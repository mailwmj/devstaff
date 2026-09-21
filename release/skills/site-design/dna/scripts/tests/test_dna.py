#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dna.py 的测试。

自带一个最小 PNG 编码器：解码是这份工具里唯一可能“静默解错”的地方，
所以它的每一条路径都要有独立锚点——先用手工算出的字节锚住滤波公式，
再用逐颜色类型的往返锚住通道排布，最后用两种交错排布锚住 Adam7 的几何。
编码器被测出的字节本身也参与断言，避免编码器和解码器用同一个错法互相“验证”。
"""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import dna  # noqa: E402

DNA_PY = HERE.parents[1] / 'dna.py'


# --------------------------------------------------------------------------
# 最小 PNG 编码器（仅测试用）
# --------------------------------------------------------------------------

def _chunk(kind, body):
    return (struct.pack('>I', len(body)) + kind + body
            + struct.pack('>I', zlib.crc32(kind + body) & 0xFFFFFFFF))


def _filter_line(line, previous, channels, filter_type):
    """编码侧滤波：解码侧逆变换的逆运算。"""
    out = bytearray(len(line))
    for index, value in enumerate(line):
        left = line[index - channels] if index >= channels else 0
        up = previous[index] if previous else 0
        up_left = previous[index - channels] if previous and index >= channels else 0
        if filter_type == 0:
            predict = 0
        elif filter_type == 1:
            predict = left
        elif filter_type == 2:
            predict = up
        elif filter_type == 3:
            predict = (left + up) >> 1
        elif filter_type == 4:
            predict = dna._paeth(left, up, up_left)
        else:
            raise ValueError(filter_type)
        out[index] = (value - predict) & 0xFF
    return bytes(out)


def _pack_rows(rows, channels, filter_type):
    """把像素行打包成带滤波字节的扫描线序列。"""
    data = bytearray()
    previous = None
    for row in rows:
        line = bytearray()
        for pixel in row:
            line.extend(pixel)
        assert len(line) == len(row) * channels
        data.append(filter_type)
        data.extend(_filter_line(line, previous, channels, filter_type))
        previous = bytes(line)
    return bytes(data)


def write_png(path, rows, color_type=2, channels=3, bit_depth=8,
              palette=None, transparency=None, interlace=0, filter_type=0):
    width = len(rows[0])
    height = len(rows)
    if interlace == 0:
        raw = _pack_rows(rows, channels, filter_type)
    else:
        raw = bytearray()
        for x_start, y_start, x_step, y_step in dna.ADAM7_PASSES:
            pass_width, pass_height = dna._adam7_geometry(
                width, height, x_start, y_start, x_step, y_step)
            if pass_width == 0 or pass_height == 0:
                continue
            tile = [[rows[y_start + row * y_step][x_start + column * x_step]
                     for column in range(pass_width)] for row in range(pass_height)]
            raw.extend(_pack_rows(tile, channels, filter_type))
        raw = bytes(raw)
    body = (b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, bit_depth,
                                          color_type, 0, 0, interlace)))
    if palette is not None:
        body += _chunk(b'PLTE', b''.join(bytes(entry) for entry in palette))
    if transparency is not None:
        body += _chunk(b'tRNS', bytes(transparency))
    body += _chunk(b'IDAT', zlib.compress(raw))
    body += _chunk(b'IEND', b'')
    Path(path).write_bytes(body)
    return raw


class Sandbox(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.dir = Path(self._dir.name)
        self.addCleanup(self._dir.cleanup)

    def path(self, name):
        return self.dir / name

    def run_dna(self, *argv):
        return subprocess.run([sys.executable, str(DNA_PY), *argv],
                              capture_output=True, text=True)


# --------------------------------------------------------------------------
# 颜色数学
# --------------------------------------------------------------------------

class ColorMathTest(unittest.TestCase):
    def test_hex_round_trip(self):
        self.assertEqual(dna.to_hex((255, 144, 232)), '#ff90e8')
        self.assertEqual(dna.parse_hex('#ff90e8'), (255, 144, 232))
        self.assertEqual(dna.parse_hex('#f0e'), (255, 0, 238))

    def test_delta_e_is_zero_for_identical_color(self):
        self.assertEqual(dna.delta_e((18, 18, 20), (18, 18, 20)), 0.0)

    def test_delta_e_catches_the_documented_perception_drift(self):
        """README 举的例子：品牌粉 #ff90e8 被“看成”常见调色板里的 #ec4899。"""
        drift = dna.delta_e(dna.parse_hex('#ff90e8'), dna.parse_hex('#ec4899'))
        self.assertGreater(drift, 20)
        self.assertEqual(dna.delta_e(dna.parse_hex('#ff90e8'), dna.parse_hex('#ff90e8')), 0.0)

    def test_hsv_keeps_near_white_unsaturated_by_hsv(self):
        """白底在 HSV 下饱和度接近 0，才不会被当成强调色。"""
        self.assertLess(dna.hsv((252, 251, 250))[1], 0.05)
        self.assertGreater(dna.hsv((255, 144, 232))[1], 0.4)

    def test_bad_hex_is_rejected_by_name(self):
        for bad in ('ff90e8', '#ff90e', '#zzzzzz', None):
            with self.assertRaises(ValueError):
                dna.parse_hex(bad)


# --------------------------------------------------------------------------
# 采样
# --------------------------------------------------------------------------

class SamplingTest(unittest.TestCase):
    def test_mix32_matches_the_upstream_javascript(self):
        """金标向量由上游 measure-colors.mjs 里的 mix32 实际跑出来（Node 22）。

        这是跨实现锚点：采样点骗了以后，”同一张图得到同一批像素“这条
        就不再成立，而整个测量都建在它上面。
        """
        golden = [(0, 1684164658), (1, 1580013426), (2, 140556409), (7, 3838393609),
                  (42, 551831576), (999, 375217065), (65535, 2369530248),
                  (1 << 20, 1276122087), (4294967295, 3950124170)]
        for value, expected in golden:
            self.assertEqual(dna.mix32(value), expected, f'mix32({value})')

    def test_sample_index_matches_the_upstream_javascript(self):
        self.assertEqual([dna.sample_index(index, 1000, 8) for index in range(8)],
                         [33, 176, 284, 445, 602, 745, 754, 984])

    def test_samples_stay_inside_their_stratum(self):
        total, count = 1000, 37
        seen = [dna.sample_index(index, total, count) for index in range(count)]
        self.assertEqual(len(set(seen)), count)  # 均匀分层，不重复
        for index, position in enumerate(seen):
            self.assertGreaterEqual(position, (index * total) // count)
            self.assertLess(position, ((index + 1) * total) // count)

    def test_sampling_is_bounded_and_deterministic(self):
        width, height = 400, 400
        rgb = bytearray()
        for index in range(width * height):
            rgb.extend(((index * 7) % 256, (index * 13) % 256, (index * 29) % 256))
        first = dna.sample_pixels(rgb, width, height)
        second = dna.sample_pixels(rgb, width, height)
        self.assertEqual(first, second)
        self.assertEqual(len(first), dna.MAX_SAMPLED_PIXELS)

    def test_sampling_keeps_periodic_detail(self):
        """1 像素隔列条纹：单相位缩放会整个抹掉，分层采样必须看到两种颜色。"""
        width, height = 200, 200
        row = bytearray()
        for column in range(width):
            row.extend((255, 255, 255) if column % 2 else (0, 0, 0))
        rgb = bytearray(row * height)
        colors = set(dna.sample_pixels(rgb, width, height))
        self.assertEqual(colors, {(0, 0, 0), (255, 255, 255)})


# --------------------------------------------------------------------------
# PNG 解码
# --------------------------------------------------------------------------

class ClusteringPortTest(unittest.TestCase):
    """聚类与角色判定的跨实现对齐。

    下面的像素集已经在 Node 里跑过上游原始的 kmeans / mergeSimilar /
    assignRoles（同一份输入、同一份上游代码），十六进制、覆盖率与角色逐项
    相同。把输入与结果固定在这里，移植以后改了任何一步都会当场报错。
    """

    # 确定性伪随机像素集：深底 + 亮字 + 高饱和强调 + 中间色 + 低占比噪点
    @staticmethod
    def pixels():
        import random
        generator = random.Random(20260921)
        out = []
        for _ in range(6000):
            roll = generator.random()
            if roll < 0.55:
                out.append((18, 18, 20))
            elif roll < 0.75:
                out.append((245, 245, 245))
            elif roll < 0.85:
                out.append((255, 144, 232))
            elif roll < 0.93:
                out.append((90, 96, 110))
            elif roll < 0.97:
                out.append((0, 110, 240))
            else:
                out.append((generator.randrange(256), generator.randrange(256),
                            generator.randrange(256)))
        return out

    def test_clusters_match_the_upstream_javascript(self):
        expected = [
            {'hex': '#121214', 'coverage': 0.5585, 'role': 'background'},
            {'hex': '#f8d3f0', 'coverage': 0.2907, 'role': 'text'},
            {'hex': '#5a606f', 'coverage': 0.0868, 'role': 'unassigned'},
            {'hex': '#026def', 'coverage': 0.0455, 'role': 'accent'},
            {'hex': '#b531aa', 'coverage': 0.0062, 'role': 'unassigned'},
            {'hex': '#d19c4c', 'coverage': 0.005, 'role': 'unassigned'},
            {'hex': '#4daa27', 'coverage': 0.004, 'role': 'unassigned'},
            {'hex': '#42d6b1', 'coverage': 0.0033, 'role': 'unassigned'},
        ]
        got = [{'hex': dna.to_hex(entry['center']),
                'coverage': round(entry['share'], 4),
                'role': entry['role']}
               for entry in dna.assign_roles(
                   dna.merge_similar(dna.kmeans(self.pixels(), 8), dna.MERGE_DELTA_E_PNG))]
        self.assertEqual(got, expected)

    def test_jpeg_reference_merges_more_aggressively(self):
        merged = dna.merge_similar(dna.kmeans(self.pixels(), 8), dna.MERGE_DELTA_E_JPEG)
        self.assertLessEqual(len(merged), 8)


class PngDecodeTest(Sandbox):
    def decode(self, name, rows, **kwargs):
        target = self.path(name)
        raw = write_png(target, rows, **kwargs)
        width, height, rgb, decoder = dna.load_rgb(target)
        return raw, width, height, rgb, decoder

    def pixels_of(self, rgb, width, height):
        return [[tuple(rgb[(row * width + column) * 3:(row * width + column) * 3 + 3])
                 for column in range(width)] for row in range(height)]

    def test_hand_computed_sub_filter_bytes(self):
        """手工锚点：3x1 RGB 用 Sub 滤波后第二、三个像素的字节是相邻差。"""
        rows = [[(10, 20, 30), (40, 50, 60), (70, 80, 90)]]
        raw, width, height, rgb, decoder = self.decode('sub.png', rows, filter_type=1)
        self.assertEqual(raw, bytes([1, 10, 20, 30, 30, 30, 30, 30, 30, 30]))
        self.assertEqual(self.pixels_of(rgb, width, height), rows)
        self.assertEqual(decoder, 'png-stdlib')

    def test_hand_computed_up_filter_bytes(self):
        """手工锚点：2x2 RGB 用 Up 滤波后第二行字节是逐通道差。"""
        rows = [[(1, 2, 3), (4, 5, 6)], [(5, 7, 9), (9, 9, 9)]]
        raw, width, height, rgb, _ = self.decode('up.png', rows, filter_type=2)
        self.assertEqual(raw, bytes([2, 1, 2, 3, 4, 5, 6, 2, 4, 5, 6, 5, 4, 3]))
        self.assertEqual(self.pixels_of(rgb, width, height), rows)

    def test_every_filter_type_round_trips(self):
        rows = [[((row * 7 + column * 11) % 256, (row * 13 + column * 3) % 256,
                  (row * 5 + column * 17) % 256)
                 for column in range(9)] for row in range(7)]
        for filter_type in range(5):
            _, width, height, rgb, _ = self.decode(f'f{filter_type}.png', rows,
                                                   filter_type=filter_type)
            self.assertEqual(self.pixels_of(rgb, width, height), rows,
                             f'filter {filter_type}')

    def test_rgba_is_flattened_onto_white(self):
        rows = [[(0, 0, 0, 0), (255, 0, 0, 128), (255, 0, 0, 255)]]
        _, width, height, rgb, _ = self.decode('rgba.png', rows, color_type=6, channels=4)
        self.assertEqual(self.pixels_of(rgb, width, height),
                         [[(255, 255, 255), (255, 127, 127), (255, 0, 0)]])

    def test_grayscale_and_grayscale_alpha(self):
        grey = [[(9,), (200,)]]
        _, width, height, rgb, _ = self.decode('grey.png', grey, color_type=0, channels=1)
        self.assertEqual(self.pixels_of(rgb, width, height),
                         [[(9, 9, 9), (200, 200, 200)]])
        grey_alpha = [[(9, 255), (200, 0)]]
        _, width, height, rgb, _ = self.decode('grey-a.png', grey_alpha, color_type=4,
                                               channels=2)
        self.assertEqual(self.pixels_of(rgb, width, height),
                         [[(9, 9, 9), (255, 255, 255)]])

    def test_palette_lookup_and_transparency(self):
        rows = [[(0,), (1,), (2,)]]
        palette = [(10, 20, 30), (200, 100, 50), (0, 0, 0)]
        _, width, height, rgb, _ = self.decode('palette.png', rows, color_type=3,
                                               channels=1, palette=palette,
                                               transparency=[255, 128, 0])
        # (200,100,50) 按 alpha=128 合成到白底 = (227,177,152)
        self.assertEqual(self.pixels_of(rgb, width, height),
                         [[(10, 20, 30), (227, 177, 152), (255, 255, 255)]])

    def test_adam7_round_trips_for_odd_sizes(self):
        """交错几何在非 8 的倍数上最容易错，用质数尺寸和逐像素唯一色锚住。"""
        for width, height in ((1, 1), (3, 5), (8, 8), (11, 13), (17, 9)):
            rows = [[((row * 31 + column * 7) % 256, (row * 17 + column * 23) % 256,
                      (row * 29 + column * 5) % 256)
                     for column in range(width)] for row in range(height)]
            _, got_width, got_height, rgb, _ = self.decode(
                f'i{width}x{height}.png', rows, interlace=1)
            self.assertEqual((got_width, got_height), (width, height))
            self.assertEqual(self.pixels_of(rgb, got_width, got_height), rows,
                             f'{width}x{height}')

    def test_multi_chunk_idat_is_concatenated(self):
        """真实 PNG 常见多个 IDAT 分块；解码要按顺序拼起来。"""
        rows = [[(1, 2, 3), (4, 5, 6)]]
        target = self.path('split.png')
        write_png(target, rows)
        whole = target.read_bytes()
        head, tail = whole.split(b'IDAT')
        # 拆成两个 IDAT 块：把原始 IDAT 内容对半切开
        marker = b'IDAT'
        start = whole.index(marker)
        length = struct.unpack('>I', whole[start - 4:start])[0]
        payload = whole[start + 4:start + 4 + length]
        rebuilt = (whole[:start - 4]
                   + _chunk(b'IDAT', payload[:1]) + _chunk(b'IDAT', payload[1:])
                   + whole[start + 4 + length + 4:])
        target.write_bytes(rebuilt)
        width, height, rgb, _ = dna.load_rgb(target)
        self.assertEqual(self.pixels_of(rgb, width, height), rows)

    def test_sixteen_bit_is_refused_with_a_remedy(self):
        target = self.path('deep.png')
        write_png(target, [[(0, 0, 0)]], color_type=2, channels=3, bit_depth=16)
        with self.assertRaises(dna.Unsupported) as caught:
            dna.load_rgb(target)
        self.assertIn('位深', str(caught.exception))

    def test_not_a_png_is_refused_with_a_remedy(self):
        target = self.path('fake.png')
        target.write_bytes(b'not a png at all')
        with self.assertRaises(dna.Unsupported):
            dna.load_rgb(target)

    def test_truncated_png_does_not_pass_silently(self):
        target = self.path('cut.png')
        write_png(target, [[(0, 0, 0)] * 4] * 4)
        whole = target.read_bytes()
        target.write_bytes(whole[:len(whole) - 20])
        with self.assertRaises(dna.Unsupported):
            dna.load_rgb(target)

    def test_ihdr_must_be_first_and_exactly_13_bytes(self):
        rows = [[(1, 2, 3)]]
        target = self.path('late-ihdr.png')
        write_png(target, rows)
        whole = target.read_bytes()
        ihdr_start = whole.index(b'IHDR') - 4
        ihdr_end = ihdr_start + 12 + 13
        ihdr = whole[ihdr_start:ihdr_end]
        gama = _chunk(b'gAMA', b'\x00\x00\x00\x01')
        target.write_bytes(whole[:ihdr_start] + gama + ihdr + whole[ihdr_end:])
        with self.assertRaises(dna.Unsupported) as caught:
            dna.load_rgb(target)
        self.assertIn('IHDR', str(caught.exception))

        target.write_bytes(
            b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', b'\x00' * 12)
            + _chunk(b'IEND', b'')
        )
        with self.assertRaises(dna.Unsupported) as caught:
            dna.load_rgb(target)
        self.assertIn('IHDR', str(caught.exception))

    def test_crc_mismatch_on_a_consumed_chunk_is_refused(self):
        rows = [[(1, 2, 3), (4, 5, 6)]]
        target = self.path('bad-crc.png')
        write_png(target, rows)
        whole = bytearray(target.read_bytes())
        marker = whole.index(b'IDAT')
        whole[marker + 4] ^= 0xFF  # flip a payload byte, leave the CRC stale
        target.write_bytes(bytes(whole))
        with self.assertRaises(dna.Unsupported) as caught:
            dna.load_rgb(target)
        self.assertIn('CRC', str(caught.exception))

    def test_ancillary_crc_is_not_parsed(self):
        rows = [[(1, 2, 3)]]
        target = self.path('ancillary-crc.png')
        write_png(target, rows)
        whole = target.read_bytes()
        ihdr_end = 8 + 12 + 13
        broken = _chunk(b'gAMA', b'\x00\x00\x00\x01')[:-1] + b'\x00'
        target.write_bytes(whole[:ihdr_end] + broken + whole[ihdr_end:])
        width, height, rgb, _ = dna.load_rgb(target)
        self.assertEqual((width, height), (1, 1))

    def test_unfilter_zero_type_truncation_is_refused(self):
        # Row 0 claims six bytes but only two follow the filter byte.
        with self.assertRaises(dna.Unsupported):
            dna._unfilter(b'\x00\x01\x02', 2, 2, 3)

    def test_non_interlaced_length_mismatch_is_refused(self):
        target = self.path('short-raw.png')
        target.write_bytes(
            b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(b'\x00' * 5))
            + _chunk(b'IEND', b'')
        )
        with self.assertRaises(dna.Unsupported):
            dna.load_rgb(target)

    def test_gray_color_key_transparency_flattens_to_white(self):
        rows = [[(10,), (200,), (10,)]]
        _, width, height, rgb, _ = self.decode(
            'grey-key.png', rows, color_type=0, channels=1, transparency=[0, 10])
        self.assertEqual(self.pixels_of(rgb, width, height),
                         [[(255, 255, 255), (200, 200, 200), (255, 255, 255)]])

    def test_rgb_color_key_transparency_flattens_to_white(self):
        rows = [[(10, 20, 30), (200, 100, 50), (10, 20, 30)]]
        _, width, height, rgb, _ = self.decode(
            'rgb-key.png', rows, color_type=2, channels=3,
            transparency=[0, 10, 0, 20, 0, 30])
        self.assertEqual(self.pixels_of(rgb, width, height),
                         [[(255, 255, 255), (200, 100, 50), (255, 255, 255)]])

    def test_wrong_trns_length_is_unsupported(self):
        target = self.path('bad-trns.png')
        write_png(target, [[(10,), (200,)]], color_type=0, channels=1,
                  transparency=[10])
        with self.assertRaises(dna.Unsupported):
            dna.load_rgb(target)

    def test_oversized_image_is_refused_before_decompression(self):
        target = self.path('huge.png')
        target.write_bytes(
            b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', 100000, 100000, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(b'\x00'))
            + _chunk(b'IEND', b'')
        )
        with self.assertRaises(dna.Unsupported) as caught:
            dna.load_rgb(target)
        self.assertIn('100000x100000', str(caught.exception))

    def test_extra_inflated_bytes_are_refused(self):
        target = self.path('extra-raw.png')
        target.write_bytes(
            b'\x89PNG\r\n\x1a\n'
            + _chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(b'\x00\x01\x02\x03' + b'\x00' * 10))
            + _chunk(b'IEND', b'')
        )
        with self.assertRaises(dna.Unsupported):
            dna.load_rgb(target)

    def test_jpeg_detection_prefers_magic_bytes_and_falls_back_to_suffix(self):
        magic_png_name = self.path('photo.png')
        magic_png_name.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 8)
        self.assertTrue(dna._is_jpeg(magic_png_name))
        png_jpg_name = self.path('image.jpg')
        png_jpg_name.write_bytes(b'\x89PNG\r\n\x1a\n')
        self.assertTrue(dna._is_jpeg(png_jpg_name))
        plain = self.path('notes.txt')
        plain.write_bytes(b'hello')
        self.assertFalse(dna._is_jpeg(plain))

    def test_decoder_remedy_follows_the_platform(self):
        import unittest.mock as mock
        with mock.patch.object(dna.sys, 'platform', 'darwin'):
            self.assertIn('sips', dna._decoder_remedy('/tmp/x.jpg'))
        with mock.patch.object(dna.sys, 'platform', 'linux'):
            self.assertIn('pip install pillow', dna._decoder_remedy('/tmp/x.jpg'))


class CrossDecoderTest(Sandbox):
    """能装上 Pillow 时，用另一个编码器/解码器对一遍。

    自带编码器和解码器可能用同一个错法互相“验证”；上面那些往返测试挡不住
    这一点。有 Pillow 时它就是那个独立验证者，没有就跳过——不因此把测试当通过。
    """

    def test_matches_pillow_on_every_channel_type(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow not installed; round-trip tests still cover the decoder')

        def expected(red, green, blue, alpha):
            if alpha == 255:
                return (red, green, blue)
            return tuple((channel * alpha + 255 * (255 - alpha)) // 255
                         for channel in (red, green, blue))

        # Pillow 12 的 putdata：多通道收元组，单通道 L 收摊平后的整数
        cases = {
            'rgb': ('RGB', lambda x, y: (x % 256, y % 256, (x + y) % 256), False),
            'rgba': ('RGBA', lambda x, y: (x % 256, y % 256, (x + y) % 256,
                                           (x * 3) % 256), False),
            'gray': ('L', lambda x, y: ((x * y) % 256,), True),
            'gray-a': ('LA', lambda x, y: ((x * y) % 256, (x + y) % 256), False),
        }
        for name, (mode, build, flatten) in cases.items():
            image = Image.new(mode, (60, 40))
            values = [build(x, y) for y in range(40) for x in range(60)]
            image.putdata([channel for pixel in values for channel in pixel]
                          if flatten else values)
            target = self.path(f'pillow-{name}.png')
            image.save(target)
            width, height, rgb, decoder = dna.load_rgb(target)
            self.assertEqual(decoder, 'png-stdlib')
            source = image.convert('RGBA').tobytes()
            for index in range(width * height):
                red, green, blue, alpha = source[index * 4:index * 4 + 4]
                self.assertEqual(
                    tuple(rgb[index * 3:index * 3 + 3]),
                    expected(red, green, blue, alpha),
                    f'{name} pixel {index}')


# --------------------------------------------------------------------------
# 测量
# --------------------------------------------------------------------------

class MeasureTest(Sandbox):
    def flat_image(self, name, blocks, width=120, height=60):
        """按覆盖率先画底色，再画几个色块，得到一份已知构成的图。"""
        pixels = [[blocks[0][0]] * width for _ in range(height)]
        cursor = 0
        for color, share in blocks[1:]:
            area = int(width * height * share)
            for index in range(area):
                position = cursor + index
                pixels[position // width][position % width] = color
            cursor += area
        target = self.path(name)
        write_png(target, pixels)
        return target

    def test_recovers_known_palette_and_roles(self):
        """深底、亮字、亮粉强调色：三个角色都要落在量出来的那三个值上。"""
        result = dna.measure(self.flat_image('page.png', [
            ((18, 18, 20), 0.90), ((245, 245, 245), 0.07), ((255, 144, 232), 0.03)]), k=4)
        palette = {entry['hex']: entry for entry in result['palette']}
        self.assertIn('#121214', palette)
        self.assertIn('#f5f5f5', palette)
        self.assertIn('#ff90e8', palette)
        self.assertEqual(palette['#121214']['role'], 'background')
        self.assertEqual(palette['#f5f5f5']['role'], 'text')
        self.assertEqual(palette['#ff90e8']['role'], 'accent')
        self.assertAlmostEqual(palette['#121214']['coverage'], 0.90, delta=0.02)

    def test_measurement_is_reproducible(self):
        target = self.flat_image('again.png', [
            ((250, 250, 248), 0.8), ((24, 24, 27), 0.15), ((20, 110, 240), 0.05)])
        self.assertEqual(dna.measure(target, 5), dna.measure(target, 5))

    def test_coverage_sums_to_one(self):
        result = dna.measure(self.flat_image('sum.png', [
            ((250, 250, 248), 0.7), ((24, 24, 27), 0.2), ((20, 110, 240), 0.1)]), k=5)
        self.assertAlmostEqual(sum(entry['coverage'] for entry in result['palette']),
                               1.0, delta=0.02)

    def test_anti_aliasing_noise_is_merged_not_reported_as_extra_colors(self):
        """把同一个色摊成相邻几档，合并后不应多报一个“新颜色”。"""
        width, height = 90, 40
        rows = []
        for row in range(height):
            line = []
            for column in range(width):
                line.append((18, 18, 20) if (row + column) % 9 else (20, 20, 22))
            rows.append(line)
        target = self.path('noise.png')
        write_png(target, rows)
        result = dna.measure(target, 8)
        self.assertEqual(len(result['palette']), 1)
        self.assertEqual(result['palette'][0]['role'], 'background')

    def test_k_is_clamped_by_the_cli(self):
        target = self.flat_image('k.png', [((250, 250, 248), 1.0)])
        done = self.run_dna('measure', str(target), '--k', '99')
        self.assertEqual(done.returncode, 0)
        self.assertEqual(json.loads(done.stdout)['measurement']['k'], 16)


# --------------------------------------------------------------------------
# 还原度比对
# --------------------------------------------------------------------------

class VerifyTest(Sandbox):
    def measurement(self, name, palette, k=8):
        target = self.path(name)
        target.write_text(json.dumps({'measurement': {'k': k}, 'palette': palette}),
                          encoding='utf-8')
        return target

    def flat(self, name, blocks, width=120, height=60):
        return MeasureTest.flat_image(self, name, blocks, width, height)

    def test_identical_palette_passes_with_zero_drift(self):
        reference = dna.measure(self.flat('ref.png', [
            ((18, 18, 20), 0.88), ((245, 245, 245), 0.08), ((255, 144, 232), 0.04)]), k=4)
        implementation = self.flat('impl.png', [
            ((18, 18, 20), 0.88), ((245, 245, 245), 0.08), ((255, 144, 232), 0.04)])
        report = dna.verify(implementation, reference)
        self.assertTrue(report['pass'])
        self.assertEqual(report['meanDeltaE'], 0.0)
        self.assertEqual(report['coverageDrift'], 0.0)

    def test_drifted_accent_color_fails(self):
        """把品牌粉换成常见默认粉：覆盖率不变，颜色误差必须让它不过。"""
        reference = dna.measure(self.flat('ref2.png', [
            ((18, 18, 20), 0.88), ((245, 245, 245), 0.08), ((255, 144, 232), 0.04)]), k=4)
        implementation = self.flat('impl2.png', [
            ((18, 18, 20), 0.88), ((245, 245, 245), 0.08), ((236, 72, 153), 0.04)])
        report = dna.verify(implementation, reference)
        self.assertFalse(report['pass'])
        self.assertGreater(report['maxDeltaE'], dna.THRESHOLD_MAX_DELTA_E)

    def test_missing_color_surfaces_as_coverage_drift(self):
        reference = dna.measure(self.flat('ref3.png', [
            ((18, 18, 20), 0.70), ((245, 245, 245), 0.10), ((255, 144, 232), 0.20)]), k=4)
        implementation = self.flat('impl3.png', [
            ((18, 18, 20), 0.90), ((245, 245, 245), 0.10)])  # 强调色整个没实现
        report = dna.verify(implementation, reference)
        self.assertFalse(report['pass'])
        self.assertGreater(report['coverageDrift'], dna.THRESHOLD_COVERAGE_DRIFT)
        dropped = [entry for entry in report['entries']
                   if entry['specHex'] == '#ff90e8'][0]
        self.assertLess(dropped['imageCoverage'], dna.SIGNIFICANT_COVERAGE)

    def test_accepts_a_design_dna_json_with_the_nested_shape(self):
        nested = self.path('dna.json')
        nested.write_text(json.dumps({
            'design_system': {'color': {
                'measurement': {'k': 4},
                'measured_palette': [
                    {'hex': '#121214', 'coverage': 0.9, 'role': 'background'},
                    {'hex': '#ff90e8', 'coverage': 0.1, 'role': 'accent'}]}}}),
            encoding='utf-8')
        implementation = self.flat('impl4.png', [
            ((18, 18, 20), 0.9), ((255, 144, 232), 0.1)])
        report = dna.verify(implementation, json.loads(nested.read_text(encoding='utf-8')))
        self.assertTrue(report['pass'])
        self.assertEqual(report['measurement']['k'], 4)

    def test_reference_without_a_palette_is_rejected(self):
        empty = self.path('empty.json')
        empty.write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            dna.verify(self.flat('x.png', [((0, 0, 0), 1.0)]), json.loads('{}'))

    def test_reference_shapes_are_validated(self):
        bad_specs = (
            [],
            {'design_system': []},
            {'design_system': {'color': []}},
            {'palette': [1]},
            {'palette': [{'hex': '#ffffff'}]},
            {'palette': [{'hex': '#ffffff', 'coverage': 'half'}]},
            {'palette': [{'hex': 'nope', 'coverage': 0.5}]},
            {'palette': [{'hex': '#ffffff', 'coverage': 0.5}], 'measurement': []},
        )
        for spec in bad_specs:
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    dna.spec_palette(spec)


# --------------------------------------------------------------------------
# 参考网址侦察
# --------------------------------------------------------------------------

def bun_shaped_recon(uploads=None):
    """一份按真实网址（bun.sh）形状造的侦察结果。

    放进来的都是实测中真正会绊倒判断的形态：CSS 变量用空格分隔通道的
    `rgb(255 31 143)`、品牌色只内嵌在焦点环里、以及名字里带 "string"
    因而含有 "ring" 的语法高亮变量。
    """
    payload = {
        'version': 1,
        'tool': 'recon.js',
        'page': {
            'url': 'https://bun.sh/', 'host': 'bun.sh', 'title': 'Bun',
            'lang': 'en', 'dir': None,
            'readyState': 'complete', 'elementCount': 4200,
            'viewport': {'width': 1440, 'height': 900, 'devicePixelRatio': 1},
            'colorScheme': 'light', 'reducedMotion': False, 'scrollHeight': 11580,
        },
        'cssVariables': {
            '--link-hover-color': 'rgb(214 0 102)',
            '--docsearch-primary-color': 'rgb(255 31 143)',
            '--ring': '0 0 0 2px rgb(255 255 255),0 0 0 4px rgb(255 31 143)',
            '--sk-string': '#4d7c1b',
            '--sk-param': '#a8520a',
            '--pink-500': '236,72,153',
            '--gray-950': '#0d0e11',
            '--tw-ring-color': '#3b82f680',
            '--c-fg-muted': '82 82 82',
            '--c-subtle': '246 246 246',
            '--navbar-height': '64px',
        },
        'roles': [
            {'role': 'html', 'selector': 'html', 'sample': '', 'fontFamily': 'sans-serif',
             'fontSize': '16px', 'fontWeight': '400', 'lineHeight': '24px',
             'letterSpacing': 'normal', 'color': 'rgb(10, 10, 10)',
             'backgroundColor': 'rgb(255, 255, 255)', 'borderRadius': '0px',
             'border': '0px none rgb(10, 10, 10)', 'boxShadow': 'none',
             'padding': '0px', 'transitionDuration': '0s',
             'transitionTimingFunction': 'ease', 'animationDuration': '0s',
             'cursor': 'auto'},
            {'role': 'body', 'selector': 'body', 'sample': 'Bun is a fast',
             'fontFamily': 'ui-sans-serif, system-ui', 'fontSize': '16px',
             'fontWeight': '400', 'lineHeight': '24px', 'letterSpacing': 'normal',
             'color': 'rgb(10, 10, 10)', 'backgroundColor': 'rgb(255, 255, 255)',
             'borderRadius': '0px', 'border': '0px none rgb(10, 10, 10)',
             'boxShadow': 'none', 'padding': '0px', 'transitionDuration': '0s',
             'transitionTimingFunction': 'ease', 'animationDuration': '0s',
             'cursor': 'auto'},
            {'role': 'h1', 'selector': 'h1.display', 'sample': 'Bun is a fast',
             'fontFamily': 'Archivo, ui-sans-serif', 'fontSize': '68px',
             'fontWeight': '800', 'lineHeight': '62.56px', 'letterSpacing': '-1.36px',
             'color': 'rgb(10, 10, 10)', 'backgroundColor': 'rgba(0, 0, 0, 0)',
             'borderRadius': '0px', 'border': '0px none rgb(10, 10, 10)',
             'boxShadow': 'none', 'padding': '0px', 'transitionDuration': '0s',
             'transitionTimingFunction': 'ease', 'animationDuration': '0s',
             'cursor': 'auto'},
            {'role': 'p', 'selector': 'p.text-pretty', 'sample': 'Runtime, package',
             'fontFamily': 'ui-sans-serif, system-ui', 'fontSize': '17.92px',
             'fontWeight': '400', 'lineHeight': '27.776px', 'letterSpacing': 'normal',
             'color': 'rgb(82, 82, 82)', 'backgroundColor': 'rgba(0, 0, 0, 0)',
             'borderRadius': '0px', 'border': '0px none rgb(82, 82, 82)',
             'boxShadow': 'none', 'padding': '0px', 'transitionDuration': '0.15s',
             'transitionTimingFunction': 'ease', 'animationDuration': '0s',
             'cursor': 'auto'},
        ],
        'scale': {
            'typeScale': [{'fontSize': '68px', 'count': 3, 'families': ['Archivo']}],
            'fontFamilies': [{'value': 'Archivo, ui-sans-serif', 'count': 12}],
            'lineHeights': [{'value': '24px', 'count': 1071}],
            'maxWidths': [{'value': '1216px', 'count': 17}],
            'borderRadii': [{'value': '9999px', 'count': 40}],
            'boxShadows': [], 'gaps': [], 'paddings': [],
            'letterSpacings': [], 'transitionDurations': [{'value': '0.15s', 'count': 179}],
            'animationDurations': [], 'easings': [],
        },
        'motion': {'accessibleStylesheets': 3, 'inaccessibleStylesheets': 0,
                   'reducedMotionRules': 6, 'keyframeRules': 17,
                   'smoothScroll': 'auto', 'stickyCount': 2, 'willChangeCount': 0},
        'effects': {
            'canvases': [], 'libraries': [],
            'scriptHosts': ['bun.sh'], 'globals': [],
            'styles': {'backdropFilter': 0, 'gradients': 1, 'mixBlendMode': 0, 'filters': 0},
            'media': {'videos': 1, 'svgs': 30, 'inlineSvgAnimations': 0, 'images': 24},
        },
        'assets': [{'src': '/logo.svg', 'host': 'bun.sh', 'alt': 'Bun',
                    'natural': '120x40', 'rendered': '120x40', 'loading': None}],
        'stylesheets': {'accessible': 3, 'inaccessible': 0},
        'notObserved': ['DOM 结构与交互结果'],
    }
    if uploads:
        payload.update(uploads)
    return payload


class ReconParseTest(unittest.TestCase):
    def test_extracts_the_result_block_from_cli_output(self):
        raw = ('### Result\n'
               '{\n  "page": {"url": "https://x.test/"},\n  "roles": [1]\n}\n'
               '### Ran Playwright code\n```js\nawait page.evaluate(...)\n```\n'
               '### Page\n- Page URL: https://x.test/\n')
        payload = dna.parse_recon(raw)
        self.assertEqual(payload['page']['url'], 'https://x.test/')

    def test_accepts_plain_json_for_other_hosts(self):
        self.assertEqual(dna.parse_recon('{"a": 1}'), {'a': 1})

    def test_result_block_at_end_of_output_is_read(self):
        self.assertEqual(dna.parse_recon('### Result\n{"a": 2}\n')['a'], 2)

    def test_output_without_a_result_block_names_the_cause(self):
        with self.assertRaises(ValueError) as caught:
            dna.parse_recon('### Page\n- Page URL: https://x.test/\n')
        self.assertIn('recon.js', str(caught.exception))


class ReconValidateTest(unittest.TestCase):
    def test_missing_fields_are_named(self):
        with self.assertRaises(ValueError) as caught:
            dna.validate_recon({'page': {}})
        self.assertIn('roles', str(caught.exception))
        self.assertIn('cssVariables', str(caught.exception))

    def test_empty_roles_is_a_failure_not_a_pass(self):
        """空样本守卫：一条选择器都没命中时，后面的判断会全部“通过”。"""
        payload = bun_shaped_recon()
        payload['roles'] = []
        with self.assertRaises(ValueError) as caught:
            dna.validate_recon(payload)
        self.assertIn('一个关键元素都没读到', str(caught.exception))

    def test_missing_url_can_be_filled_in(self):
        payload = bun_shaped_recon()
        payload['page']['url'] = None
        dna.validate_recon(payload, 'https://example.test/')
        self.assertEqual(payload['page']['url'], 'https://example.test/')

    def test_non_object_collections_are_named(self):
        for payload in (
            {'page': [], 'cssVariables': {}, 'roles': [{}]},
            {'page': {}, 'cssVariables': [], 'roles': [{}]},
            {'page': {}, 'cssVariables': {}, 'roles': 'nope'},
            {'page': {}, 'cssVariables': {}, 'roles': ['html']},
            {'page': {}, 'cssVariables': {}, 'roles': [{}], 'notes': 'x'},
            {'page': {}, 'cssVariables': {}, 'roles': [{}], 'assets': 'x'},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    dna.validate_recon(payload)

    def test_half_loaded_page_is_flagged(self):
        """没加载完的页面与“这个站就这么简单”长得一样，只能靠这两个数分开。"""
        payload = bun_shaped_recon()
        payload['page']['readyState'] = 'loading'
        payload['page']['elementCount'] = 12
        dna.validate_recon(payload)
        notes = ' '.join(payload['notes'])
        self.assertIn('readyState', notes)
        self.assertIn('空壳页', notes)

    def test_a_settled_page_gets_no_such_note(self):
        payload = bun_shaped_recon()
        dna.validate_recon(payload)
        self.assertFalse(payload.get('notes'))

    def test_no_css_variables_is_a_note_not_a_failure(self):
        payload = bun_shaped_recon()
        payload['cssVariables'] = {}
        dna.validate_recon(payload)
        self.assertTrue(any('没有声明 CSS 变量' in note for note in payload['notes']))


class ReconColorFormatTest(unittest.TestCase):
    def test_accepts_the_formats_real_sites_use(self):
        for value in ('#2f5fd0', '#3b82f680', 'rgb(255 31 143)', 'rgb(214, 0, 102)',
                      'rgba(255, 255, 255, 0.5)', 'oklch(0.7 0.15 20)'):
            self.assertIsNotNone(dna._color_style(value), value)

    def test_rejects_bare_channel_triples_and_shorthands(self):
        """`246 246 246` 看起来像颜色，但没有形式能证明它是；不猜。"""
        for value in ('246 246 246', '82 82 82', '0 0 #0000', '64px', 'none', ''):
            self.assertIsNone(dna._color_style(value), value)

    def test_finds_a_color_embedded_in_a_shape(self):
        found = dna._embedded_colors('0 0 0 2px rgb(255 255 255),0 0 0 4px rgb(255 31 143)')
        self.assertIn('rgb(255 31 143)', found)

    def test_does_not_dig_into_a_value_that_is_already_a_color(self):
        self.assertEqual(dna._embedded_colors('rgb(255 31 143)'), [])


class ReconNameAffinityTest(unittest.TestCase):
    def test_syntax_variable_is_not_matched_by_a_substring_of_ring(self):
        """`--sk-string` 含有 "ring" 四个字母，但和焦点环没关系。"""
        weight, reasons = dna._name_affinity('--sk-string')
        self.assertNotIn('+ring', reasons)
        self.assertIn('-sk-', reasons)
        self.assertLess(weight, 1)

    def test_semantic_names_rank_above_palette_scales(self):
        semantic = dna._name_affinity('--docsearch-primary-color')[0]
        scale = dna._name_affinity('--pink-500')[0]
        self.assertGreater(semantic, scale)
        self.assertIn('-色阶', dna._name_affinity('--pink-500')[1])

    def test_tailwind_internal_keeps_both_marks(self):
        _weight, reasons = dna._name_affinity('--tw-ring-color')
        self.assertIn('+ring', reasons)
        self.assertIn('-tw-', reasons)


class ReconCandidateTest(unittest.TestCase):
    def test_brand_color_beats_syntax_highlighting(self):
        candidates = dna.recon_candidates(bun_shaped_recon())
        values = [candidate['value'] for candidate in candidates['accent']]
        self.assertIn('rgb(255 31 143)', values)
        self.assertIn('rgb(214 0 102)', values)
        top_two = {candidate['value'] for candidate in candidates['accent'][:2]}
        self.assertEqual(top_two, {'rgb(214 0 102)', 'rgb(255 31 143)'})

    def test_every_accent_candidate_says_where_it_came_from(self):
        for candidate in dna.recon_candidates(bun_shaped_recon())['accent']:
            self.assertTrue(candidate['source'], candidate)
            self.assertTrue(candidate['reason'], candidate)

    def test_embedded_brand_color_is_found_through_the_ring(self):
        payload = bun_shaped_recon()
        del payload['cssVariables']['--docsearch-primary-color']
        sources = [candidate['source']
                   for candidate in dna.recon_candidates(payload)['accent']]
        self.assertTrue(any('--ring' in source for source in sources), sources)

    def test_role_candidates_point_at_their_element(self):
        candidates = dna.recon_candidates(bun_shaped_recon())
        self.assertEqual(candidates['canvas'][0]['value'], 'rgb(255, 255, 255)')
        self.assertIn('html backgroundColor', candidates['canvas'][0]['source'])
        # html 与 body 都给出来：两者不一致时（body 透明、背景挂在 html 上）要能看出来
        self.assertTrue(any('body backgroundColor' in candidate['source']
                            for candidate in candidates['canvas']))
        self.assertEqual(candidates['text'][0]['value'], 'rgb(10, 10, 10)')
        self.assertIn('h1 color', candidates['text'][0]['source'])

    def test_only_non_brand_colors_is_flagged_for_a_second_look(self):
        payload = bun_shaped_recon()
        payload['cssVariables'] = {'--sk-param': '#a8520a', '--sk-string': '#4d7c1b'}
        payload['roles'] = [entry for entry in payload['roles']
                            if entry['role'] in ('html', 'body')]
        candidates = dna.recon_candidates(payload)
        self.assertTrue(candidates['notes'], candidates)

    def test_duplicate_embedded_color_is_counted_once(self):
        payload = bun_shaped_recon()
        payload['cssVariables'] = {
            '--focus-shadow': '0 0 0 2px rgb(255 31 143),0 0 0 4px rgb(255 31 143)'
        }
        payload['roles'] = [entry for entry in payload['roles'] if entry['role'] == 'body']
        candidates = dna.recon_candidates(payload)
        values = [candidate['value'] for candidate in candidates['accent']]
        self.assertEqual(values.count('rgb(255 31 143)'), 1)


class ReconSummaryTest(unittest.TestCase):
    def test_summary_is_bounded_and_carries_the_scales(self):
        summary = dna.recon_summary(bun_shaped_recon(), '/tmp/recon.json')
        self.assertEqual(summary['page']['url'], 'https://bun.sh/')
        self.assertEqual(summary['counts']['cssVariables'], 11)
        self.assertTrue(summary['typeScale'])
        self.assertTrue(summary['lineHeights'])
        self.assertTrue(summary['maxWidths'])
        self.assertEqual(summary['report'], '/tmp/recon.json')
        self.assertLess(len(json.dumps(summary)), 6000)

    def test_summary_says_what_was_not_observed(self):
        summary = dna.recon_summary(bun_shaped_recon())
        self.assertTrue(summary['notObserved'])


class ReconCliTest(Sandbox):
    def write_raw(self, name='recon.raw'):
        target = self.path(name)
        target.write_text('### Result\n'
                          + json.dumps(bun_shaped_recon(), ensure_ascii=False)
                          + '\n### Ran Playwright code\n```js\n```\n',
                          encoding='utf-8')
        return target

    def test_reads_cli_output_and_writes_the_evidence_file(self):
        raw = self.write_raw()
        out = self.path('recon.json')
        done = self.run_dna('recon', str(raw), '--out', str(out), '--summary')
        self.assertEqual(done.returncode, 0)
        summary = json.loads(done.stdout)
        self.assertEqual(summary['mode'], 'summary')
        self.assertEqual(json.loads(out.read_text(encoding='utf-8')),
                         bun_shaped_recon())

    def test_empty_roles_exits_one_instead_of_reporting_success(self):
        payload = bun_shaped_recon()
        payload['roles'] = []
        target = self.path('empty.json')
        target.write_text(json.dumps(payload), encoding='utf-8')
        done = self.run_dna('recon', str(target))
        self.assertEqual(done.returncode, 1)
        self.assertIn('一个关键元素都没读到', done.stderr)

    def test_stdin_input_is_accepted(self):
        done = subprocess.run(
            [sys.executable, str(DNA_PY), 'recon', '-', '--summary'],
            input=json.dumps(bun_shaped_recon()), capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['mode'], 'summary')


# --------------------------------------------------------------------------
# 命令行
# --------------------------------------------------------------------------

class CliTest(Sandbox):
    def image(self, name):
        rows = [[((row * 11) % 256, (column * 13) % 256, 90) for column in range(40)]
                for row in range(40)]
        target = self.path(name)
        write_png(target, rows)
        return target

    def test_measure_writes_out_and_prints(self):
        target = self.image('cli.png')
        out = self.path('measured.json')
        done = self.run_dna('measure', str(target), '--out', str(out))
        self.assertEqual(done.returncode, 0)
        printed = json.loads(done.stdout)
        self.assertEqual(printed, json.loads(out.read_text(encoding='utf-8')))
        self.assertTrue(printed['measured'])
        self.assertEqual(printed['source']['width'], 40)
        self.assertEqual(printed['measurement']['decoder'], 'png-stdlib')

    def test_verify_exit_codes_are_distinct(self):
        reference = self.path('cli-ref.json')
        image = self.image('cli2.png')
        measured = dna.measure(image, 4)
        reference.write_text(json.dumps(measured), encoding='utf-8')
        passed = self.run_dna('verify', str(image), str(reference))
        self.assertEqual(passed.returncode, 0)
        self.assertTrue(json.loads(passed.stdout)['pass'])

        measured['palette'] = [dict(entry, hex='#010203') for entry in measured['palette']]
        reference.write_text(json.dumps(measured), encoding='utf-8')
        failed = self.run_dna('verify', str(image), str(reference), '--summary')
        self.assertEqual(failed.returncode, 2)
        self.assertFalse(json.loads(failed.stdout)['pass'])
        self.assertIn('FAIL', failed.stderr)

    def test_unreadable_image_exits_one_with_a_remedy(self):
        target = self.path('broken.png')
        target.write_bytes(b'not a png')
        done = self.run_dna('measure', str(target))
        self.assertEqual(done.returncode, 1)
        # 补救动作按平台不同（macOS 是 sips，其他地方是 Pillow/ImageMagick）。
        # 平台分支本身由 test_decoder_remedy_follows_the_platform 覆盖，
        # 这条 CLI 测试只要求确实给出一条在当前平台可执行的补救。
        self.assertIn('没有可用的替代解码器', done.stderr)
        self.assertTrue('sips' in done.stderr or 'pip install pillow' in done.stderr,
                        done.stderr)

    def test_malformed_inputs_report_machine_readable_errors(self):
        image = self.image('machine.png')
        bad_spec = self.path('bad-spec.json')
        bad_spec.write_text(json.dumps({'design_system': [], 'palette': []}), encoding='utf-8')
        done = self.run_dna('verify', str(image), str(bad_spec))
        self.assertEqual(done.returncode, 1)
        self.assertNotIn('Traceback', done.stderr)
        self.assertTrue(json.loads(done.stderr)['error'])

        bad_recon = self.path('bad-recon.json')
        bad_recon.write_text(json.dumps({'page': [], 'cssVariables': [], 'roles': 'x'}),
                             encoding='utf-8')
        done = self.run_dna('recon', str(bad_recon))
        self.assertEqual(done.returncode, 1)
        self.assertNotIn('Traceback', done.stderr)
        self.assertTrue(json.loads(done.stderr)['error'])


if __name__ == '__main__':
    unittest.main()
