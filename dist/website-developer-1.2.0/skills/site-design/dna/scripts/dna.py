#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""确定性取色与还原度比对。

把“像不像那个网站”从感觉变成可以复跑的数：从参考截图里量出精确色板
（k-means 聚类 + CIE ΔE 合并 + 覆盖率 + 角色判定），再拿实现截图与这份
色板比对，算出每种颜色的 ΔE 与覆盖率偏差，给出 PASS/FAIL。

上游：zanwei/design-dna（MIT）的 scripts/measure-colors.mjs 与
scripts/verify.mjs，版权与出处见同目录上层 dna/LICENSE 与 dna/VERSION。
本文件按本项目的约束重新实现：**只用 Python 标准库**，PNG 自带解码，
不引入 Node 与 sharp；算法（确定性分层采样、最远点初始化的 k-means、
ΔE 合并阈值、角色判定、PASS/FAIL 阈值）与上游一致。

用法：
    python3 dna.py measure <参考截图> [--k 8] [--out FILE]
    python3 dna.py verify <实现截图> <测量或 DNA JSON> [--out FILE] [--summary]

退出码：measure 成功 0；verify 通过 0、不通过 2、无法测量 1。

为什么不用眼睛估色：模型对颜色的感知会向常见调色板默认值漂移，实测中
品牌粉 #ff90e8 会被“看成”#ec4899（ΔE≈29）。估出来的值写进合同后无法
核对，看起来却像测量结果。这个脚本负责给出可核对的那一份。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import struct
import zlib
from pathlib import Path

MASK32 = 0xFFFFFFFF
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
MAX_SAMPLED_PIXELS = 160000
KMEANS_ITERATIONS = 24
# 抗锯齿与 JPEG 噪声都会把一个平色摊成几个邻近聚类，先合并再判定角色。
MERGE_DELTA_E_PNG = 2.5
MERGE_DELTA_E_JPEG = 5.0
SIGNIFICANT_COVERAGE = 0.005
# 上游阈值。改这里等于改“还原到什么程度算过”，要有实际使用依据再动。
THRESHOLD_MEAN_DELTA_E = 5.0
THRESHOLD_MAX_DELTA_E = 20.0
THRESHOLD_COVERAGE_DRIFT = 0.35
ROLE_UNASSIGNED = 'unassigned'

# Adam7 交错法的 7 趟：(x 起点, y 起点, x 步长, y 步长)
ADAM7_PASSES = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
                (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
# PNG 颜色类型 -> 每像素通道数
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
JPEG_SUFFIXES = ('.jpg', '.jpeg', '.jpe', '.jfif')
JPEG_MAGIC = b'\xff\xd8\xff'
# 解压前的像素上限：4K 屏（~830 万像素）不误伤，同时挡住把内存吃光的万像素图。
MAX_DECODED_PIXELS = 50_000_000
# 只有被消费的块才做 CRC 校验；ancillary 块跳过不解析。
CONSUMED_CHUNKS = frozenset({b'IHDR', b'PLTE', b'tRNS', b'IDAT', b'IEND'})


def _is_jpeg(path, header=None):
    """按文件头判定 JPEG，扩展名只作兜底；下载来的参考图常被改名。"""
    if header is None:
        try:
            header = Path(path).read_bytes()[:3]
        except OSError:
            header = b''
    if header.startswith(JPEG_MAGIC):
        return True
    return Path(path).suffix.lower() in JPEG_SUFFIXES


class Unsupported(Exception):
    """图片读不了：说清原因和可用的替代动作，不猜一个值出来。"""


# --------------------------------------------------------------------------
# 颜色数学（CIE76 ΔE，与上游 color-math.mjs 同式）
# --------------------------------------------------------------------------

def srgb_to_lab(rgb):
    def linear(value):
        value /= 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(channel) for channel in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(value):
        return value ** (1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116

    x, y, z = f(x), f(y), f(z)
    return (116 * y - 16, 500 * (x - y), 200 * (y - z))


def delta_e(a, b):
    return math.dist(srgb_to_lab(a), srgb_to_lab(b))


def to_hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, int(round(value)))):02x}' for value in rgb)


def parse_hex(text):
    if not isinstance(text, str) or len(text) not in (4, 7) or not text.startswith('#'):
        raise ValueError(f'expected a #rgb or #rrggbb color, got {text!r}')
    if len(text) == 4:
        text = '#' + ''.join(channel * 2 for channel in text[1:])
    try:
        return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        raise ValueError(f'expected a #rgb or #rrggbb color, got {text!r}')


def hsv(rgb):
    """色相（度）、HSV 饱和度、HSL 亮度。

    强调色判定用 HSV 饱和度：接近白色的颜色在 HSL 下饱和度会虚高，
    会把白底误判成品牌色。与上游同式。
    """
    r, g, b = (channel / 255.0 for channel in rgb)
    high, low = max(r, g, b), min(r, g, b)
    spread = high - low
    saturation = 0.0 if high == 0 else spread / high
    lightness = (high + low) / 2
    hue = 0.0
    if spread != 0:
        if high == r:
            hue = 60 * (((g - b) / spread) % 6)
        elif high == g:
            hue = 60 * ((b - r) / spread + 2)
        else:
            hue = 60 * ((r - g) / spread + 4)
    return ((hue + 360) % 360, saturation, lightness)


# --------------------------------------------------------------------------
# 图片解码
# --------------------------------------------------------------------------

def _paeth(left, up, up_left):
    estimate = left + up - up_left
    left_gap = abs(estimate - left)
    up_gap = abs(estimate - up)
    up_left_gap = abs(estimate - up_left)
    if left_gap <= up_gap and left_gap <= up_left_gap:
        return left
    return up if up_gap <= up_left_gap else up_left


def _unfilter(data, width, height, channels):
    """撤销逐扫描线滤波，返回 row-major 的原始样本字节。"""
    stride = width * channels
    out = bytearray(height * stride)
    position = 0
    previous = bytearray(stride)
    for row in range(height):
        if position >= len(data):
            raise Unsupported(f'PNG 数据在扫描线 {row} 处截断')
        filter_type = data[position]
        position += 1
        if filter_type == 0:
            # 无滤波是最常见的一种，直接搬字节，不用先复制再回写。
            # 长度不够时切片会静默变短，必须在这里挡住。
            if position + stride > len(data):
                raise Unsupported(f'PNG 数据在扫描线 {row} 处截断')
            out[row * stride:(row + 1) * stride] = data[position:position + stride]
            previous = out[row * stride:(row + 1) * stride]
            position += stride
            continue
        line = bytearray(data[position:position + stride])
        if len(line) != stride:
            raise Unsupported(f'PNG 数据在扫描线 {row} 处截断')
        position += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up_left = previous[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, previous[i], up_left)) & 0xFF
        else:
            raise Unsupported(f'PNG 用了未知的滤波类型 {filter_type}')
        out[row * stride:(row + 1) * stride] = line
        previous = line
    return out


def _png_chunks(raw):
    """依次产出 (kind, body, crc_bytes)；块长度与实际字节对不上时拒绝。"""
    position = len(PNG_SIGNATURE)
    while position + 8 <= len(raw):
        length = struct.unpack('>I', raw[position:position + 4])[0]
        kind = raw[position + 4:position + 8]
        body_start = position + 8
        body_end = body_start + length
        if body_end + 4 > len(raw):
            raise Unsupported('PNG 数据在块 %s 处截断' % kind.decode('ascii', 'replace'))
        yield kind, raw[body_start:body_end], raw[body_end:body_end + 4]
        position = body_end + 4


def _adam7_geometry(width, height, x_start, y_start, x_step, y_step):
    """一趟交错子图的 (宽, 高)；边角趟可能为空。"""
    pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
    pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
    return pass_width, pass_height


def _scatter_pass(target, tile, width, channels, pass_width, pass_height,
                  x_start, y_start, x_step, y_step):
    """把一趟解好滤波的子图写进整幅画面的样本缓冲。"""
    stride = pass_width * channels
    for row in range(pass_height):
        target_row = y_start + row * y_step
        source_row = row * stride
        for column in range(pass_width):
            source = source_row + column * channels
            destination = (target_row * width + x_start + column * x_step) * channels
            target[destination:destination + channels] = tile[source:source + channels]


def _png_samples(path):
    """解码 PNG，返回 (宽, 高, 每像素通道字节, 每像素通道数, 调色板, 透明表)。

    只支持 8 位深：截图都是这一档，其余档位如实报不支持并给出替代动作，
    而不是按猜的位数解出一批错的颜色。
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise Unsupported(f'读不了 {path}：{error}')
    if not raw.startswith(PNG_SIGNATURE):
        raise Unsupported(f'{path} 不是 PNG 文件')

    header = None
    palette = None
    transparency = None
    compressed = bytearray()
    seen_iend = False
    first_chunk = True
    for kind, body, crc in _png_chunks(raw):
        if first_chunk and kind != b'IHDR':
            raise Unsupported(f'{path} 的第一个 PNG 块不是 IHDR')
        first_chunk = False
        if kind in CONSUMED_CHUNKS:
            expected_crc = zlib.crc32(kind + body) & MASK32
            found_crc = struct.unpack('>I', crc)[0]
            if found_crc != expected_crc:
                raise Unsupported(
                    'PNG 块 %s 的 CRC 校验失败：数据已损坏'
                    % kind.decode('ascii', 'replace'))
        if kind == b'IHDR':
            if len(body) != 13:
                raise Unsupported(f'{path} 的 IHDR 长度是 {len(body)}，应为 13 字节')
            try:
                header = struct.unpack('>IIBBBBB', body)
            except struct.error as error:
                raise Unsupported(f'{path} 的 IHDR 无法解析：{error}')
        elif kind == b'PLTE':
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body) - len(body) % 3, 3)]
        elif kind == b'tRNS':
            transparency = bytes(body)
        elif kind == b'IDAT':
            compressed += body
        elif kind == b'IEND':
            seen_iend = True
            break
    if header is None:
        raise Unsupported(f'{path} 缺少 IHDR，不是完整的 PNG')
    if not seen_iend:
        raise Unsupported(f'{path} 缺少 IEND，PNG 数据不完整')
    width, height, depth, color_type, compression, filter_method, interlace = header
    if width == 0 or height == 0:
        raise Unsupported(f'{path} 的尺寸是 {width}x{height}')
    if depth != 8:
        raise Unsupported(f'{path} 是 {depth} 位深 PNG，本脚本只解 8 位深；'
                          '请先转成 8 位 PNG（如 sips -s format png）再量')
    if color_type not in PNG_CHANNELS:
        raise Unsupported(f'{path} 的 PNG 颜色类型 {color_type} 不支持')
    if compression != 0 or filter_method != 0:
        raise Unsupported(f'{path} 用了非标准的 PNG 压缩或滤波方式')
    if interlace not in (0, 1):
        raise Unsupported(f'{path} 的 PNG 交错方式 {interlace} 不支持')
    channels = PNG_CHANNELS[color_type]
    if color_type == 3 and not palette:
        raise Unsupported(f'{path} 是索引色 PNG 但没有 PLTE 调色板')

    # 解压前先按声明的尺寸算原始字节数，把像素上限和长度预算一起定下来；
    # 动辄上亿像素的图不能等解压完才拒绝。
    if width * height > MAX_DECODED_PIXELS:
        raise Unsupported(
            f'{path} 的尺寸是 {width}x{height}（{width * height} 像素），'
            f'超过 {MAX_DECODED_PIXELS} 像素的解码上限；请先缩小再量')
    if interlace == 0:
        expected_raw = height * (width * channels + 1)
    else:
        expected_raw = 0
        for x_start, y_start, x_step, y_step in ADAM7_PASSES:
            pass_width, pass_height = _adam7_geometry(
                width, height, x_start, y_start, x_step, y_step)
            expected_raw += pass_height * (pass_width * channels + 1)

    try:
        decompressor = zlib.decompressobj()
        inflated = decompressor.decompress(bytes(compressed), expected_raw + 1)
    except zlib.error as error:
        raise Unsupported(f'{path} 的 PNG 像素数据解压失败：{error}')
    if len(inflated) > expected_raw or decompressor.unconsumed_tail:
        raise Unsupported(f'{path} 的 PNG 像素数据超过了声明的尺寸')
    if not decompressor.eof or decompressor.unused_data:
        raise Unsupported(f'{path} 的 PNG 像素数据长度对不上，拒绝按猜的结果出数')

    if interlace == 0:
        if len(inflated) != expected_raw:
            raise Unsupported(
                f'{path} 的非交错 PNG 数据长度 {len(inflated)} 与尺寸不符（应为 {expected_raw})')
        samples = _unfilter(inflated, width, height, channels)
    else:
        samples = bytearray(width * height * channels)
        cursor = 0
        for x_start, y_start, x_step, y_step in ADAM7_PASSES:
            pass_width, pass_height = _adam7_geometry(
                width, height, x_start, y_start, x_step, y_step)
            if pass_width == 0 or pass_height == 0:
                continue
            # 每一趟的扫描线有自己的滤波字节，所以要按趟单独解滤波。
            span = pass_width * pass_height * channels + pass_height
            tile = _unfilter(inflated[cursor:cursor + span],
                             pass_width, pass_height, channels)
            cursor += span
            _scatter_pass(samples, tile, width, channels,
                          pass_width, pass_height, x_start, y_start, x_step, y_step)
        if cursor != len(inflated):
            raise Unsupported(f'{path} 的交错 PNG 数据长度对不上，拒绝按猜的结果出数')

    return width, height, samples, channels, color_type, palette, transparency


def _samples_to_rgb(samples, channels, color_type, palette, transparency):
    """转成 row-major RGB 字节，透明像素按白底合成（与上游 flatten 一致）。

    没有 alpha 的格式直接返回样本本身，不白跑一遍逐像素循环。
    """
    if color_type == 2:
        if transparency is None:
            return samples
        if len(transparency) != 6:
            raise Unsupported('RGB PNG 的 tRNS 色键应为 6 字节')
        key = struct.unpack('>HHH', transparency)
        rgb = bytearray(samples)
        for index in range(len(samples) // 3):
            base = index * 3
            if (samples[base], samples[base + 1], samples[base + 2]) == key:
                # 色键像素即全透明，按白底合成后就是白色。
                rgb[base:base + 3] = b'\xff\xff\xff'
        return rgb
    if color_type == 0:
        grey = bytearray(len(samples) * 3)
        grey[0::3] = samples
        grey[1::3] = samples
        grey[2::3] = samples
        if transparency is not None:
            if len(transparency) != 2:
                raise Unsupported('灰度 PNG 的 tRNS 色键应为 2 字节')
            key = struct.unpack('>H', transparency)[0]
            for index, sample in enumerate(samples):
                if sample == key:
                    offset = index * 3
                    grey[offset:offset + 3] = b'\xff\xff\xff'
        return grey
    pixels = len(samples) // channels
    originals = palette if color_type == 3 else None
    rgb = bytearray(pixels * 3)
    for index in range(pixels):
        base = index * channels
        alpha = 255
        if color_type == 3:
            entry = samples[base]
            if entry >= len(originals):
                raise Unsupported('索引色 PNG 的调色板索引越界')
            red, green, blue = originals[entry]
            if transparency is not None and entry < len(transparency):
                alpha = transparency[entry]
        elif color_type == 4:
            grey, alpha = samples[base:base + 2]
            red = green = blue = grey
        else:  # color_type == 6
            red, green, blue, alpha = samples[base:base + 4]
        if alpha != 255:
            red = (red * alpha + 255 * (255 - alpha)) // 255
            green = (green * alpha + 255 * (255 - alpha)) // 255
            blue = (blue * alpha + 255 * (255 - alpha)) // 255
        offset = index * 3
        rgb[offset] = red
        rgb[offset + 1] = green
        rgb[offset + 2] = blue
    return rgb


def _convert_with(tool, path):
    """用外部工具转成 8 位 PNG，返回临时文件路径；不可用时返回 None。"""
    suffix = '.png'
    target = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    target.close()
    if tool == 'sips':
        argv = ['sips', '-s', 'format', 'png', str(path), '--out', target.name]
    else:
        argv = [tool, str(path), '-depth', '8', target.name]
    try:
        done = subprocess.run(argv, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        Path(target.name).unlink(missing_ok=True)
        return None
    if done.returncode != 0 or not Path(target.name).stat().st_size:
        Path(target.name).unlink(missing_ok=True)
        return None
    return target.name


def _decoder_remedy(path):
    """没有可用解码器时按平台给出可执行的下一步。"""
    if sys.platform == 'darwin':
        return f'sips -s format png "{path}" --out reference.png'
    return 'python3 -m pip install pillow（或安装 ImageMagick 后用 magick/convert）'


def load_rgb(path):
    """读成 (宽, 高, RGB 字节, 解码器名)。解码器名如实记录进报告。

    优先自带 PNG 解码（无损、确定）；其余格式依序尝试可选的替代解码器。
    按文件头而不仅按扩展名判断，因为下载下来的参考图常被改名。
    一个解码器都没有就报 `unsupported` 并给出可执行的替代动作——不返回猜的值。
    """
    try:
        header = Path(path).read_bytes()[:8]
    except OSError as error:
        raise Unsupported(f'读不了 {path}：{error}')
    if header == PNG_SIGNATURE:
        width, height, samples, channels, color_type, palette, transparency = _png_samples(path)
        return (width, height,
                _samples_to_rgb(samples, channels, color_type, palette, transparency),
                'png-stdlib')

    tried = []
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        tried.append('Pillow 未安装')
    else:
        tried.append('Pillow')
        try:
            with Image.open(path) as handle:
                flattened = handle.convert('RGBA')
                width, height = flattened.size
                rgb = bytearray(width * height * 3)
                source = flattened.tobytes()
                for index in range(width * height):
                    red, green, blue, alpha = source[index * 4:index * 4 + 4]
                    if alpha != 255:
                        red = (red * alpha + 255 * (255 - alpha)) // 255
                        green = (green * alpha + 255 * (255 - alpha)) // 255
                        blue = (blue * alpha + 255 * (255 - alpha)) // 255
                    rgb[index * 3:index * 3 + 3] = bytes((red, green, blue))
                return width, height, rgb, 'pillow'
        except Exception:  # Pillow 认不出这个文件，继续试下一种
            pass
    for tool in ('sips', 'magick', 'convert'):
        if shutil.which(tool) is None:
            continue
        tried.append(tool)
        converted = _convert_with(tool, path)
        if converted is None:
            continue
        try:
            width, height, samples, channels, color_type, palette, transparency = _png_samples(converted)
            return (width, height,
                    _samples_to_rgb(samples, channels, color_type, palette, transparency),
                    f'{tool}(8bit-png)')
        finally:
            Path(converted).unlink(missing_ok=True)
    requested = Path(path).suffix or '(无扩展名)'
    raise Unsupported(
        f'{path}（{requested}）不是 PNG，也没有可用的替代解码器（试过：{", ".join(tried)}）。'
        f'请先转成 8 位 PNG 再量：{_decoder_remedy(path)}')


# --------------------------------------------------------------------------
# 确定性采样
# --------------------------------------------------------------------------

def mix32(value):
    """与上游同式的 32 位混合哈希；同样的图必须给出同样的采样点。"""
    def imul(a, b):
        return (a * b) & MASK32

    x = (value + 0x9E3779B9) & MASK32
    x = imul(x ^ (x >> 16), 0x21F0AAAD)
    x = imul(x ^ (x >> 15), 0x735A2D97)
    return (x ^ (x >> 15)) & MASK32


def sample_index(sample, total_pixels, sample_count):
    start = (sample * total_pixels) // sample_count
    end = ((sample + 1) * total_pixels) // sample_count
    return start + (mix32(sample) % max(1, end - start))


def sample_pixels(rgb, width, height):
    """把整幅图按等长分层取一个真实像素，采样量与图像大小无关且可复现。

    单次最近邻缩放永远在同一相位取样，会把周期性细节整个抹掉（例如 1 像素
    隔行条纹）；分层加固定哈希既限制采样数，又不引入插值出来的新颜色。
    """
    total_pixels = width * height
    sample_count = min(total_pixels, MAX_SAMPLED_PIXELS)
    pixels = []
    for sample in range(sample_count):
        offset = sample_index(sample, total_pixels, sample_count) * 3
        pixels.append((rgb[offset], rgb[offset + 1], rgb[offset + 2]))
    if len(pixels) != sample_count:
        raise Unsupported(f'期望采样 {sample_count} 个像素，实际取到 {len(pixels)} 个')
    return pixels


# --------------------------------------------------------------------------
# 聚类与角色判定
# --------------------------------------------------------------------------

def kmeans(pixels, k):
    """最远点初始化的 k-means：先取最暗像素，再反复取离已有中心最远的像素，
    让占比小但确实不同的颜色也能分到自己的聚类。"""
    ordered = sorted(pixels, key=lambda pixel: pixel[0] * 3 + pixel[1] * 6 + pixel[2])
    centers = [list(ordered[0])]
    nearest = [float('inf')] * len(pixels)
    while len(centers) < k:
        last = centers[-1]
        farthest, farthest_distance = 0, -1.0
        for index, pixel in enumerate(pixels):
            distance = ((pixel[0] - last[0]) ** 2 + (pixel[1] - last[1]) ** 2
                        + (pixel[2] - last[2]) ** 2)
            if distance < nearest[index]:
                nearest[index] = distance
            if nearest[index] > farthest_distance:
                farthest_distance, farthest = nearest[index], index
        if farthest_distance <= 0:
            break  # 实际颜色数少于 k
        centers.append(list(pixels[farthest]))
    k = len(centers)
    assignment = [0] * len(pixels)
    for _ in range(KMEANS_ITERATIONS):
        moved = False
        for index, pixel in enumerate(pixels):
            best, best_distance = 0, float('inf')
            for cluster, center in enumerate(centers):
                distance = ((pixel[0] - center[0]) ** 2 + (pixel[1] - center[1]) ** 2
                            + (pixel[2] - center[2]) ** 2)
                if distance < best_distance:
                    best_distance, best = distance, cluster
            if assignment[index] != best:
                assignment[index] = best
                moved = True
        sums = [[0.0, 0.0, 0.0, 0] for _ in range(k)]
        for index, pixel in enumerate(pixels):
            bucket = sums[assignment[index]]
            bucket[0] += pixel[0]
            bucket[1] += pixel[1]
            bucket[2] += pixel[2]
            bucket[3] += 1
        for cluster, bucket in enumerate(sums):
            if bucket[3]:
                centers[cluster] = [bucket[0] / bucket[3], bucket[1] / bucket[3],
                                    bucket[2] / bucket[3]]
        if not moved:
            break
    counts = [0] * k
    for cluster in assignment:
        counts[cluster] += 1
    clusters = [{'center': center, 'share': counts[index] / len(pixels)}
                for index, center in enumerate(centers) if counts[index] > 0]
    clusters.sort(key=lambda entry: entry['share'], reverse=True)
    return clusters


def merge_similar(clusters, max_delta_e):
    merged = []
    for cluster in clusters:
        near = None
        for candidate in merged:
            if delta_e(candidate['center'], cluster['center']) <= max_delta_e:
                near = candidate
                break
        if near is None:
            merged.append({'center': list(cluster['center']), 'share': cluster['share']})
        else:
            total = near['share'] + cluster['share']
            near['center'] = [(value * near['share'] + other * cluster['share']) / total
                              for value, other in zip(near['center'], cluster['center'])]
            near['share'] = total
    merged.sort(key=lambda entry: entry['share'], reverse=True)
    return merged


def assign_roles(clusters):
    entries = []
    for cluster in clusters:
        hue, saturation, lightness = hsv(cluster['center'])
        entries.append({'center': cluster['center'], 'share': cluster['share'],
                        'h': hue, 's': saturation, 'l': lightness,
                        'role': ROLE_UNASSIGNED})
    taken = set()
    entries[0]['role'] = 'background'
    taken.add(0)
    background_lightness = entries[0]['l']
    text, best_contrast = -1, 0.0
    for index, entry in enumerate(entries):
        if index in taken:
            continue
        contrast = abs(entry['l'] - background_lightness)
        if entry['share'] >= 0.005 and contrast > best_contrast:
            best_contrast, text = contrast, index
    if text >= 0 and best_contrast > 0.25:
        entries[text]['role'] = 'text'
        taken.add(text)
    # 强调色同时看饱和度和与背景的感知距离；覆盖率只用来压掉极小的噪点簇，
    # 一旦某种颜色占到 2%，面积大的浅色块就不能压过面积小但很亮的 CTA。
    accents = []
    for index, entry in enumerate(entries):
        if index in taken or entry['s'] < 0.25 or entry['share'] < 0.002:
            continue
        if not 0.08 <= entry['l'] <= 0.92:
            continue
        accents.append((entry['s'] * delta_e(entry['center'], entries[0]['center'])
                        * math.sqrt(min(entry['share'], 0.02) / 0.02), index))
    if accents:
        accents.sort(key=lambda item: item[0], reverse=True)
        best = accents[0][1]
        entries[best]['role'] = 'accent'
        taken.add(best)
    return entries


def measure(path, k=8):
    """量一张图，返回与上游 measure-colors.mjs 同形的结果。"""
    width, height, rgb, decoder = load_rgb(path)
    pixels = sample_pixels(rgb, width, height)
    is_jpeg = _is_jpeg(path)
    clusters = merge_similar(kmeans(pixels, k),
                             MERGE_DELTA_E_JPEG if is_jpeg else MERGE_DELTA_E_PNG)
    palette = assign_roles(clusters)
    return {
        'source': {'file': Path(path).name, 'path': str(Path(path)),
                   'width': width, 'height': height},
        'measurement': {
            'k': k,
            'decoder': decoder,
            'sampling': {'method': 'deterministic_stratified',
                         'max_pixels': MAX_SAMPLED_PIXELS,
                         'sampled_pixels': len(pixels)},
            'merge_delta_e': MERGE_DELTA_E_JPEG if is_jpeg else MERGE_DELTA_E_PNG,
        },
        'palette': [{'hex': to_hex(entry['center']),
                     'coverage': round(entry['share'], 4),
                     'role': entry['role']} for entry in palette],
        'measured': True,
    }


# --------------------------------------------------------------------------
# 还原度比对
# --------------------------------------------------------------------------

def _nested_design_color(spec):
    """spec.design_system.color 的形状校验；缺失时返回 {}。"""
    design_system = spec.get('design_system')
    if design_system is None:
        return {}
    if not isinstance(design_system, dict):
        raise ValueError('design_system 必须是一个 JSON 对象')
    color = design_system.get('color')
    if color is None:
        return {}
    if not isinstance(color, dict):
        raise ValueError('design_system.color 必须是一个 JSON 对象')
    return color


def spec_palette(spec):
    """从测量结果或 DNA JSON 里取出参考色板与它的聚类配置。

    形状不对就报错，不猜：一个填错的 spec 若被当成空色板，验证会
    在“没有参考”的情况下算出一个看似通过的分数。
    """
    if not isinstance(spec, dict):
        raise ValueError('参考文件必须是一个 JSON 对象')
    color = _nested_design_color(spec)
    palette = spec.get('palette')
    if palette is None:
        palette = color.get('measured_palette')
    if not isinstance(palette, list):
        raise ValueError('palette 必须是一个数组')
    if not palette:
        raise ValueError('参考文件里没有 palette / design_system.color.measured_palette 数组')
    for entry in palette:
        if not isinstance(entry, dict):
            raise ValueError('参考色板每一项都必须是一个 JSON 对象')
        if 'hex' not in entry or 'coverage' not in entry:
            raise ValueError('参考色板每一项都要有 hex 与 coverage')
        parse_hex(entry['hex'])
        coverage = entry['coverage']
        if isinstance(coverage, bool) or not isinstance(coverage, (int, float)):
            raise ValueError(f'参考色板的 coverage 必须是数字，得到 {coverage!r}')
    measurement = spec.get('measurement')
    if measurement is None:
        measurement = color.get('measurement')
    if measurement is None:
        measurement = {}
    if not isinstance(measurement, dict):
        raise ValueError('measurement 必须是一个 JSON 对象')
    try:
        k = int(measurement.get('k', 8))
    except (TypeError, ValueError):
        k = 8
    return palette, max(2, min(16, k))


def verify(implementation_path, spec):
    """用同一套确定性流程重新量实现截图，与参考色板比对。

    两边的聚类配置必须一致（k 与算法），否则比的是参数差异不是设计差异。
    """
    reference, k = spec_palette(spec)
    measured = measure(implementation_path, k)
    implementation = measured['palette']

    def nearest(color, candidates):
        best, best_distance = None, float('inf')
        for candidate in candidates:
            distance = delta_e(parse_hex(color), parse_hex(candidate['hex']))
            if distance < best_distance:
                best_distance, best = distance, candidate
        return best, best_distance

    assigned = [[] for _ in reference]
    for cluster in implementation:
        index, _ = min(
            ((position, delta_e(parse_hex(entry['hex']), parse_hex(cluster['hex'])))
             for position, entry in enumerate(reference)),
            key=lambda item: item[1])
        _, distance = nearest(reference[index]['hex'], [cluster])
        assigned[index].append({'hex': cluster['hex'], 'coverage': cluster['coverage'],
                                'delta_e': distance})

    significant_image = [entry for entry in implementation
                         if entry['coverage'] >= SIGNIFICANT_COVERAGE]
    entries = []
    for position, entry in enumerate(reference):
        group = assigned[position]
        coverage = sum(item['coverage'] for item in group)
        # 参考里占比明显的颜色必须对上一个占比明显的实现聚类：不足千分之五
        # 的残影不算保住了这个颜色。
        candidates = (significant_image
                      if entry['coverage'] >= SIGNIFICANT_COVERAGE and significant_image
                      else implementation)
        match, distance = nearest(entry['hex'], candidates)
        entries.append({
            'specHex': entry['hex'],
            'role': entry.get('role', ROLE_UNASSIGNED),
            'nearestImageHex': match['hex'] if match else None,
            'deltaE': round(distance, 2),
            'specCoverage': entry['coverage'],
            'imageCoverage': round(coverage, 4),
        })

    # 实现侧的每个聚类单独参与颜色误差评分：一个占了不少面积但颜色错的块，
    # 不能被平均进邻近的参考色里藏起来。
    implementation_clusters = []
    for cluster in implementation:
        match, distance = nearest(cluster['hex'], reference)
        implementation_clusters.append({
            'imageHex': cluster['hex'],
            'imageCoverage': cluster['coverage'],
            'nearestSpecHex': match['hex'] if match else None,
            'nearestSpecRole': match.get('role', ROLE_UNASSIGNED) if match else None,
            'deltaE': round(distance, 2),
        })

    # 平均 ΔE 以实现里实际出现的面积加权；覆盖率偏差与参考侧最大值负责暴露
    # 被整体漏掉的颜色。
    weight = sum(item['imageCoverage'] for item in implementation_clusters)
    mean_delta_e = (sum(item['deltaE'] * item['imageCoverage']
                        for item in implementation_clusters) / weight) if weight else 0.0
    drift = sum(abs(entry['specCoverage'] - entry['imageCoverage']) for entry in entries)
    max_implementation = max([0.0] + [item['deltaE'] for item in implementation_clusters
                                      if item['imageCoverage'] >= SIGNIFICANT_COVERAGE])
    # 反向也要看：参考里占比明显的颜色如果整个没实现，实现侧就没有聚类可评。
    max_reference = max([0.0] + [entry['deltaE'] for entry in entries
                                 if entry['specCoverage'] >= SIGNIFICANT_COVERAGE])
    max_delta_e = max(max_implementation, max_reference)
    passed = (mean_delta_e <= THRESHOLD_MEAN_DELTA_E and max_delta_e <= THRESHOLD_MAX_DELTA_E
              and drift <= THRESHOLD_COVERAGE_DRIFT)
    return {
        'implementation': str(Path(implementation_path)),
        'implementation_measurement': {'decoder': measured['measurement']['decoder'], 'k': k},
        'measurement': {'k': k},
        'entries': entries,
        'implementationClusters': implementation_clusters,
        'meanDeltaE': round(mean_delta_e, 2),
        'maxDeltaE': round(max_delta_e, 2),
        'coverageDrift': round(drift, 4),
        'thresholds': {'meanDeltaE': THRESHOLD_MEAN_DELTA_E,
                       'maxDeltaE': THRESHOLD_MAX_DELTA_E,
                       'coverageDrift': THRESHOLD_COVERAGE_DRIFT,
                       'significantCoverage': SIGNIFICANT_COVERAGE},
        'pass': passed,
    }


def verify_summary(report, path=None):
    """结论的短版本。标签必须跟着 pass 走：一个失败的比对印出 PASS，
    就是这套工具最不能犯的错。"""
    label = 'PASS' if report['pass'] else 'FAIL'
    return {
        'mode': 'summary',
        'pass': report['pass'],
        'meanDeltaE': report['meanDeltaE'],
        'maxDeltaE': report['maxDeltaE'],
        'coverageDrift': report['coverageDrift'],
        'thresholds': report['thresholds'],
        'measurement': report['measurement'],
        'report': str(path) if path else None,
        'verdict': (f"{label} — mean ΔE {report['meanDeltaE']}, "
                    f"max ΔE {report['maxDeltaE']}, "
                    f"coverage drift {report['coverageDrift']}"),
    }


# --------------------------------------------------------------------------
# 参考网址侦察（本地代码，不是上游移植）
#
# measure / verify 移植自 design-dna；recon 是本项目自己的：网址这一路的主证据
# 不在像素里，在 CSS 里——字体名、字号/行高/字距绝对值、圆角、阴影、动效时长与
# 曲线、脚本依赖，这些都是浏览器算完的精确值，截图一个都给不了。截图的活是
# 当验收基准。这一段只做两件事：把浏览器吐回来的结果收成项目证据格式，
# 以及给一个不会把上下文灌满的摘要视图。
# --------------------------------------------------------------------------

RECON_RESULT_MARKER = '### Result'
WELL_FORMED_COLOR = re.compile(
    r'^(?:#[0-9a-fA-F]{3,8}'
    r'|rgba?\([0-9.,%\s/]+\)'
    r'|hsla?\([0-9.,%\s/deg]+\)'
    r'|oklch\([^()]+\)'
    r'|oklab\([^()]+\)'
    r'|lab\([^()]+\)'
    r'|lch\([^()]+\))$')
# 只认颜色值，不认形状。没有形式的取值单独计数：既不说它是颜色，也不假装没看见。
UNVALIDATED_COLOR = re.compile(r'^[\d.,%\s]+$')


def parse_recon(raw_text):
    """从宿主浏览器工具的输出里取出侦察结果。

    `playwright-cli eval` 会把结果夹在 `### Result` 与下一个 `### ` 之间，其余是它
    自己的回执。也直接吃纯 JSON，因为宿主工具不一定是它。
    """
    stripped = raw_text.strip()
    if stripped.startswith('{'):
        return json.loads(stripped)
    lines = raw_text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == RECON_RESULT_MARKER:
            start = index + 1
            continue
        if start is not None and line.startswith('### '):
            return json.loads('\n'.join(lines[start:index]))
    if start is not None:
        return json.loads('\n'.join(lines[start:]))
    raise ValueError(
        f'输出里既没有直接的 JSON，也没有 `{RECON_RESULT_MARKER}` 段。'
        '确认你执行的是 dna/scripts/recon.js，且结果没有被日志混进来。')


def validate_recon(payload, url=None):
    """形状检查。**空样本一律判失败**：选择器一条都没命中时 roles 是空数组，
    后面所有基于它的判断都会“通过”，而实际上什么都没看到。"""
    if not isinstance(payload, dict):
        raise ValueError('侦察结果必须是一个 JSON 对象')
    missing = [key for key in ('page', 'cssVariables', 'roles')
               if payload.get(key) is None]
    if missing:
        raise ValueError(
            '侦察结果缺字段：' + '、'.join(missing)
            + '；这份结果不是 recon.js 产出的，不要当成证据用')
    if not isinstance(payload['page'], dict):
        raise ValueError('侦察结果的 page 必须是 JSON 对象')
    if not isinstance(payload['cssVariables'], dict):
        raise ValueError('侦察结果的 cssVariables 必须是 JSON 对象')
    if not isinstance(payload['roles'], list):
        raise ValueError('侦察结果的 roles 必须是数组')
    for index, entry in enumerate(payload['roles']):
        if not isinstance(entry, dict):
            raise ValueError(f'侦察结果的 roles[{index}] 必须是 JSON 对象')
    for key in ('notes', 'assets'):
        if payload.get(key) is not None and not isinstance(payload[key], list):
            raise ValueError(f'侦察结果的 {key} 必须是数组')

    def add_note(message):
        notes = payload.get('notes')
        if notes is None:
            notes = []
            payload['notes'] = notes
        notes.append(message)

    if not payload['roles']:
        raise ValueError(
            '侦察结果里 roles 是空的：一个关键元素都没读到。'
            '这通常是页面没加载完或跑在了 about:blank 上，不是“这个站没有样式”。')
    if not payload['cssVariables']:
        # CSS 变量可能真的没有（很多站不用），所以只提醒不拦。
        add_note('这个站没有声明 CSS 变量，颜色只能从 roles 与频次里读')
    page = payload['page']
    ready = page.get('readyState')
    if ready and ready != 'complete':
        # 没加载完的页面与“这个站就这么简单”长得一样，区别只能从这里看出来。
        add_note(
            f'取数时页面 readyState 是 {ready}，DOM 可能还没长完；'
            '等加载完再跑一次，否则读到的是一份不完整的证据')
    elements = page.get('elementCount')
    if isinstance(elements, int) and elements < 50:
        add_note(
            f'整页只有 {elements} 个元素，很可能还没渲染完或就是个空壳页；'
            '先确认你打开的是要看的那一页，再拿这份结果下结论')
    if url and not page.get('url'):
        page['url'] = url
    return payload


def _color_style(value):
    """算一个颜色值的饱和度与亮度；不是颜色就返回 None。"""
    if not isinstance(value, str) or not WELL_FORMED_COLOR.match(value.strip()):
        return None
    text = value.strip()
    if text.startswith('#'):
        try:
            rgb = parse_hex(text[:7] if len(text) >= 7 else text)
        except ValueError:
            return None
    else:
        numbers = [part for part in re.split(r'[^0-9.]+', text) if part]
        if len(numbers) < 3:
            return None
        try:
            rgb = tuple(int(float(number)) for number in numbers[:3])
        except ValueError:
            return None
        if any(channel > 255 for channel in rgb):
            return None
    return hsv(rgb)


EMBEDDED_COLOR = re.compile(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b'
                            r'|rgba?\([0-9.,%\s/]+\)'
                            r'|oklch\([^()]+\)|hsl[a]?\([0-9.,%\s/deg]+\)')


def _embedded_colors(value):
    """从不是颜色的值里把内嵌的颜色挖出来。

    品牌色常常藏在形状里而不是单独一个变量里：bun.sh 的品牌粉只出现在
    `--ring: 0 0 0 2px rgb(255 255 255),0 0 0 4px rgb(255 31 143)` 这样的
    焦点环里。只看“值本身是不是颜色”会把它整条丢掉。
    """
    if not isinstance(value, str) or _color_style(value):
        return []
    return [match for match in EMBEDDED_COLOR.findall(value) if _color_style(match)]


# 变量名里的词是有意义的：只看饱和度会选出语法高亮配色而不是品牌色。
NAME_AFFINITY = (
    (3.0, ('brand', 'accent', 'primary', 'cta', 'link', 'focus', 'ring',
           'highlight', 'selection', 'action')),
    (0.2, ('sk-', '-sk', 'code', 'syntax', 'hljs', 'prism', 'shiki', 'token',
           'editor', 'terminal', 'ansi')),
    (0.35, ('gray', 'grey', 'neutral', 'slate', 'zinc', 'stone', 'tw-',
            'shadow', 'radius', 'blur', 'font', 'spacing', 'step', 'ease',
            'duration', 'delay', 'z-', 'opacity', 'scale', 'rotate', 'translate')),
)


def _name_affinity(name):
    """返回 (权重, 理由)。带调色板色阶后缀的值再降一档：那是一条色阶，
    不等于这个站实际用了哪一档。

    按词段匹配，不做纯子串包含：`--sk-string` 里含有 `ring` 四个字母，但它跟焦点环
    没有关系，误配一次就会把语法高亮配色推到品牌色前面。
    """
    lowered = (name or '').lower()
    segments = set(re.split(r'[-_]+', lowered.lstrip('-')))
    reasons = []
    weight = 1.0
    for factor, needles in NAME_AFFINITY:
        hit = next((needle for needle in needles
                    if needle in segments
                    or (needle.endswith('-') and needle in lowered)
                    or ('-' in needle and needle in lowered)), None)
        if hit:
            weight *= factor
            reasons.append(('+' if factor > 1 else '-') + hit)
    if re.search(r'-\d{2,3}$', lowered) and 'brand' not in segments:
        weight *= 0.5
        reasons.append('-色阶')
    return weight, reasons


def recon_candidates(payload):
    """从侦察结果里提出语义角色的候选值，每个都带来源。

    只给候选，不给结论：一个站可能有两个同饱和度的品牌色，选哪个是内容决定的，
    不是脚本能决定的。合同里的最终值要人看一眼再写。
    """
    roles = payload.get('roles') or []
    by_role = {}
    for entry in roles:
        if isinstance(entry, dict) and entry.get('role'):
            by_role.setdefault(entry['role'], entry)

    def from_role(role, field):
        entry = by_role.get(role)
        if not entry:
            return None
        value = entry.get(field)
        if not value:
            return None
        return {'value': value, 'source': f"{role} {field}（{entry.get('selector', '')}）"}

    canvas = [candidate for candidate in (from_role('html', 'backgroundColor'),
                                          from_role('body', 'backgroundColor'))
              if candidate]
    text = [candidate for candidate in (from_role('h1', 'color'), from_role('body', 'color'),
                                        from_role('p', 'color')) if candidate]
    muted = [candidate for candidate in (from_role('p', 'color'), from_role('code', 'color'))
             if candidate]

    # 强调色从 CSS 变量与关键元素里找。变量名猜不到
    # （bun.sh 的品牌色在 --docsearch-primary-color 里，还内嵌在 --ring 里），
    # 所以全部遍历；但名字比饱和度更可靠，所以两者一起算。
    pool = []
    unvalidated = 0
    for name, value in (payload.get('cssVariables') or {}).items():
        if _color_style(value):
            weight, reasons = _name_affinity(name)
            pool.append({'value': value, 'source': f'CSS 变量 {name}',
                         'affinity': weight, 'reason': reasons})
            continue
        embedded = _embedded_colors(value)
        if embedded:
            weight, reasons = _name_affinity(name)
            # dict.fromkeys 按首次出现顺序去重；原来的 index() 对重复颜色
            # 取的是第一个下标，同一颜色会在池里出现两次。
            for found in dict.fromkeys(embedded[:2]):
                pool.append({'value': found, 'source': f'CSS 变量 {name}（内嵌）',
                             'affinity': weight, 'reason': reasons + ['内嵌在形状里']})
            continue
        if isinstance(value, str) and UNVALIDATED_COLOR.match(value.strip()):
            unvalidated += 1
    for role in ('button', 'a', 'badge', 'card'):
        for field in ('backgroundColor', 'color', 'borderTopColor'):
            candidate = from_role(role, field)
            if candidate:
                pool.append(dict(candidate, affinity=1.0, reason=['关键元素']))
    scored = []
    for candidate in pool:
        style = _color_style(candidate['value'])
        if not style:
            continue
        saturation, lightness = style[1], style[2]
        if saturation < 0.25 or not 0.08 <= lightness <= 0.92:
            continue
        scored.append((saturation * candidate['affinity'], candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    accent = [dict(candidate, score=round(score, 3)) for score, candidate in scored[:5]]
    notes = []
    if accent and all(candidate.get('affinity', 1.0) < 1 for candidate in accent):
        notes.append(
            '进前几名的高饱和颜色都来自非品牌语义的变量名（语法高亮、调色板色阶这类），'
            '很可能是误报。按名字再找一遍：常见品牌色变量名是 brand / primary / '
            'accent / link / focus / ring；也可能只出现在暗色主题里。')
    return {'canvas': canvas[:2], 'text': text[:3], 'muted': muted[:2], 'accent': accent,
            'unvalidatedColorLikeVariables': unvalidated, 'notes': notes}


def recon_summary(payload, path=None):
    """有上限的摘要视图。一份没有上限的侦察结果会把上下文灌满，
    而真正要判的只是几个刻度值。"""
    page = payload.get('page') or {}
    roles = payload.get('roles') or []
    effects = payload.get('effects') or {}
    scale = payload.get('scale') or {}
    motion = payload.get('motion') or {}
    stylesheets = payload.get('stylesheets') or {}
    variables = payload.get('cssVariables') or {}
    color_variables = sum(1 for value in variables.values() if _color_style(value))
    candidates = recon_candidates(payload)
    colourless = {key: value for key, value in candidates.items()
                  if key not in ('unvalidatedColorLikeVariables', 'notes') and value}
    return {
        'mode': 'summary',
        'report': str(path) if path else None,
        'page': {
            'url': page.get('url'), 'host': page.get('host'), 'title': page.get('title'),
            'viewport': page.get('viewport'), 'colorScheme': page.get('colorScheme'),
            'lang': page.get('lang'),
            # 摘要里也要能看出“没加载完”，否则只读摘要的人会把不完整的证据当完整
            'readyState': page.get('readyState'), 'elementCount': page.get('elementCount'),
        },
        'counts': {
            'cssVariables': len(variables),
            'colorVariables': color_variables,
            'roles': len(roles),
            'assets': len(payload.get('assets') or []),
            'canvases': len(effects.get('canvases') or []),
        },
        'candidates': colourless,
        'candidateNotes': candidates.get('notes') or [],
        'unvalidatedColorLikeVariables': candidates['unvalidatedColorLikeVariables'],
        'fonts': (scale.get('fontFamilies') or [])[:4],
        'typeScale': (scale.get('typeScale') or [])[:8],
        'lineHeights': (scale.get('lineHeights') or [])[:4],
        'maxWidths': (scale.get('maxWidths') or [])[:4],
        'radii': (scale.get('borderRadii') or [])[:4],
        'shadows': (scale.get('boxShadows') or [])[:3],
        'effects': {
            'canvases': effects.get('canvases') or [],
            'libraries': (effects.get('libraries') or [])[:8],
            'globals': effects.get('globals') or [],
            'gradients': (effects.get('styles') or {}).get('gradients', 0),
            'backdropFilter': (effects.get('styles') or {}).get('backdropFilter', 0),
            'videos': (effects.get('media') or {}).get('videos', 0),
            'inlineSvgAnimations': (effects.get('media') or {}).get('inlineSvgAnimations', 0),
        },
        'motion': {
            'durations': (scale.get('transitionDurations') or [])[:4],
            'easings': (scale.get('easings') or [])[:4],
            'reducedMotionRules': motion.get('reducedMotionRules', 0),
            'keyframeRules': motion.get('keyframeRules', 0),
        },
        'stylesheets': stylesheets,
        'notObserved': payload.get('notObserved') or [],
        'notes': payload.get('notes') or [],
    }


# --------------------------------------------------------------------------
# 命令行
# --------------------------------------------------------------------------

def _dump(payload, out, summary=None):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    path = None
    if out:
        path = Path(out).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + '\n', encoding='utf-8')
        path = path.resolve()
    print(json.dumps(summary(path) if summary else payload, ensure_ascii=False, indent=2))
    return path


def _fail(message):
    """把错误印成机器可读的一行 JSON，不吐 traceback。"""
    print(json.dumps({'error': str(message)}, ensure_ascii=False), file=sys.stderr)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Measure a reference screenshot deterministically, then score an '
                    'implementation against that palette.')
    commands = parser.add_subparsers(dest='command', required=True)

    measure_cmd = commands.add_parser('measure', help='measure a reference image')
    measure_cmd.add_argument('image')
    measure_cmd.add_argument('--k', type=int, default=8,
                             help='number of clusters, clamped to 2..16 (default: 8)')
    measure_cmd.add_argument('--out', help='also write the full measurement JSON here')

    verify_cmd = commands.add_parser('verify', help='score an implementation screenshot')
    verify_cmd.add_argument('image')
    verify_cmd.add_argument('reference', help='measurement JSON or Design DNA JSON')
    verify_cmd.add_argument('--out', help='also write the full report here')
    verify_cmd.add_argument('--summary', action='store_true',
                            help='print the verdict and counts only; full report goes to --out')

    recon_cmd = commands.add_parser(
        'recon', help='read a browser reconnaissance result into the project evidence format')
    recon_cmd.add_argument('source', nargs='?', default='-',
                           help='playwright-cli output or plain JSON; - reads stdin')
    recon_cmd.add_argument('--url', help='fill in the page URL when the host did not report one')
    recon_cmd.add_argument('--out', help='write the normalized reconnaissance here')
    recon_cmd.add_argument('--summary', action='store_true',
                           help='print counts, role candidates and scales only; '
                                'the full result goes to --out')

    args = parser.parse_args(argv)
    try:
        if args.command == 'measure':
            _dump(measure(args.image, max(2, min(16, args.k))), args.out)
            return 0
        if args.command == 'recon':
            if args.source == '-':
                raw = sys.stdin.read()
            else:
                try:
                    raw = Path(args.source).read_text(encoding='utf-8')
                except OSError as error:
                    return _fail(f'读不了侦察结果：{error}')
            try:
                payload = parse_recon(raw)
            except json.JSONDecodeError as error:
                return _fail(f'侦察结果不是合法 JSON：{error}')
            payload = validate_recon(payload, args.url)
            # 与 design.py 的报告命令同一个约定：--out 落完整结果，
            # --summary 只印有上限的视图，不产生第二份真相。
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            path = None
            if args.out:
                path = Path(args.out).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text + '\n', encoding='utf-8')
                path = path.resolve()
            if args.summary:
                print(json.dumps(recon_summary(payload, path), ensure_ascii=False, indent=2))
            else:
                print(text)
            return 0
        try:
            spec = json.loads(Path(args.reference).read_text(encoding='utf-8'))
        except OSError as error:
            return _fail(f'读不了参考文件：{error}')
        except json.JSONDecodeError as error:
            return _fail(f'参考文件不是合法 JSON：{error}')
        if not isinstance(spec, dict):
            return _fail('参考文件必须是 JSON 对象')
        report = verify(args.image, spec)
        _dump(report, args.out,
              (lambda path: verify_summary(report, path)) if args.summary else None)
        if not report['pass']:
            print(verify_summary(report)['verdict'], file=sys.stderr)
        return 0 if report['pass'] else 2
    except Unsupported as error:
        return _fail(error)
    except (ValueError, OSError, KeyError) as error:
        return _fail(error)


if __name__ == '__main__':
    sys.exit(main())
