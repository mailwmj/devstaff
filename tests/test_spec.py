"""Pin the facts ``AI-EMPLOYEE-SPEC.md`` claims about the package.

The archive drifted before: it named the 1.1.0 artifact after the release had
moved to 1.2.0, and it documented showcase assets that never shipped. Those are
exactly the mistakes this module prevents. Only claims a machine can check are
asserted here; judgement calls stay in the document.

Python 3.9+, standard library only.
"""

import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "release"
SPEC = ROOT / "AI-EMPLOYEE-SPEC.md"

ICON_BOX = (564, 576)
AVATAR_BOX = (360, 360)
SHOWCASE_BOX = (1600, 900)
ICON_COUNT = 4
SHOWCASE_COUNT = 4
QUICK_PROMPT_COUNT = 3
SCENE_COUNT = 4


def metadata():
    return json.loads((RELEASE / "metadata.json").read_text(encoding="utf-8"))


def home_scenes():
    return json.loads((RELEASE / "agent" / "home.json").read_text(encoding="utf-8"))["scenes"]


def bound_skill_ids():
    text = (RELEASE / "agent" / "bindings.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s*-\s*id:\s*(\S+)\s*$", text, re.M)


def bindings():
    """(id, source, required) for every declared binding."""
    text = (RELEASE / "agent" / "bindings.yaml").read_text(encoding="utf-8")
    pattern = re.compile(
        r"-\s*id:\s*(?P<id>[\w.-]+)\s*(?:\n\s+\S+:.*)*?\n\s*required:\s*(?P<required>true|false)\s*$",
        re.M,
    )
    return [(m.group("id"), m.group("required")) for m in pattern.finditer(text)]


def png_box(path):
    with path.open("rb") as handle:
        header = handle.read(24)
    return struct.unpack(">II", header[16:24])


def package_relative(path):
    """Turn a ``./agent/...`` metadata path into a path under ``release/``."""
    return RELEASE / path.lstrip("./")


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.text = SPEC.read_text(encoding="utf-8")
        self.meta = metadata()
        self.agent = self.meta["agent"]

    def test_stated_package_version_matches_metadata(self):
        match = re.search(r"对应包版本[：:]\s*\*{0,2}([0-9]+\.[0-9]+\.[0-9]+)", self.text)
        self.assertIsNotNone(match, "档案缺少「对应包版本」一行")
        self.assertEqual(self.meta["version"], match.group(1))

    def test_documented_artifact_names_use_the_current_version(self):
        mentioned = set(re.findall(r"website-developer-([0-9]+\.[0-9]+\.[0-9]+)", self.text))
        self.assertEqual(
            mentioned - {self.meta["version"]},
            set(),
            "档案里出现过期的包名；改用 release/metadata.json 的版本",
        )

    def test_referenced_release_paths_exist(self):
        paths = set(re.findall(r"`(release/[A-Za-z0-9_./\-]*\.[A-Za-z0-9]+)`", self.text))
        self.assertTrue(paths, "档案里没有可校验的 release/ 路径")
        for rel in sorted(paths):
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).is_file(), f"{rel} 未随包交付")

    def test_every_bound_skill_is_documented_with_its_version(self):
        for skill_id in bound_skill_ids():
            with self.subTest(skill=skill_id):
                row = next(
                    (line for line in self.text.splitlines() if line.startswith(f"| `{skill_id}` ")),
                    None,
                )
                self.assertIsNotNone(row, f"§七 缺少 {skill_id} 一行")
                version = (RELEASE / "skills" / skill_id / "VERSION").read_text(encoding="utf-8").strip()
                self.assertIn(version, row, f"{skill_id} 版本与 VERSION 文件不一致")

    def test_every_workspace_scene_is_documented(self):
        scenes = home_scenes()
        self.assertEqual(len(scenes), SCENE_COUNT)
        for scene in scenes:
            with self.subTest(scene=scene["id"]):
                self.assertIn(scene["id"], self.text)
                self.assertIn(scene["name"], self.text)
                icon = RELEASE / "agent" / scene["icon"].lstrip("./")
                self.assertTrue(icon.is_file(), f"{scene['id']} 的图标缺失")

    def test_every_bound_skill_is_a_hard_dependency(self):
        declared = bindings()
        self.assertEqual(len(declared), 4, "绑定解析失败，检查 bindings.yaml 格式")
        for skill_id, required in declared:
            with self.subTest(skill=skill_id):
                self.assertEqual(
                    required,
                    "true",
                    f"{skill_id} 标成非硬依赖；guided 流程缺它就跑不通，要改先看档案 §七",
                )

    def test_every_quick_prompt_is_documented(self):
        prompts = self.agent["quickPrompts"]
        self.assertEqual(len(prompts), QUICK_PROMPT_COUNT)
        for prompt in prompts:
            with self.subTest(prompt=prompt["id"]):
                self.assertIn(prompt["id"], self.text)

    def test_showcases_are_documented_and_shipped(self):
        showcases = self.agent["showcases"]
        self.assertEqual(len(showcases), SHOWCASE_COUNT)
        for showcase in showcases:
            with self.subTest(showcase=showcase["id"]):
                self.assertIn(f"`{showcase['id']}`", self.text)
                # 客户端把卡片标题写死为空，只渲染 description 一句文案
                self.assertIn(showcase["description"], self.text, f"{showcase['id']} 的文案没有进档案")
                self.assertLessEqual(len(showcase["description"]), 34, "卡片文案要能在两行内读完")
                self.assertEqual(showcase["mediaType"], "image")
                self.assertEqual(showcase["usage"], "marketplace-preview")
                self.assertTrue(package_relative(showcase["path"]).is_file())

    def test_documented_pixel_sizes_match_the_shipped_assets(self):
        self.assertIn(f"{ICON_BOX[0]} × {ICON_BOX[1]}", self.text)
        self.assertIn(f"{AVATAR_BOX[0]} × {AVATAR_BOX[1]}", self.text)
        self.assertIn(f"{SHOWCASE_BOX[0]} × {SHOWCASE_BOX[1]}", self.text)

        icons = sorted((RELEASE / "agent" / "assets" / "home").glob("*.png"))
        self.assertEqual(len(icons), ICON_COUNT, f"能力卡图标应为 {ICON_COUNT} 个")
        for icon in icons:
            measured = png_box(icon)
            with self.subTest(icon=icon.name):
                self.assertEqual(measured, ICON_BOX, f"{icon.name} 实测 {measured}")

        showcases = sorted((RELEASE / "agent" / "assets" / "showcases").glob("*.png"))
        self.assertEqual(len(showcases), SHOWCASE_COUNT)
        for showcase in showcases:
            measured = png_box(showcase)
            with self.subTest(showcase=showcase.name):
                self.assertEqual(measured, SHOWCASE_BOX, f"{showcase.name} 实测 {measured}")

        avatar = RELEASE / "agent" / "assets" / "logo.png"
        self.assertEqual(png_box(avatar), AVATAR_BOX)
        self.assertIn("./agent/assets/logo.png", self.meta["icon"])
        self.assertTrue(package_relative(self.meta["icon"]).is_file())


if __name__ == "__main__":
    unittest.main()
