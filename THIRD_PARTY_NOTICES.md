# 第三方内容与许可说明

核对日期：2026-09-07。本文件记录当前本地 Windows 框架使用的软件、字体和资料。各内容保留各自许可；本文件不为游戏原创代码指定开源许可证。

## Python、PySide6 与 Qt

运行环境使用 CPython 3.12.13。运行时随附的许可已原样复制至 `docs/licenses/CPython-3.12.13-LICENSE.txt`，原路径与 SHA-256 见 `docs/licenses/sources.json`。

本地 PySide6、PySide6 Essentials、PySide6 Addons 和 Shiboken6 均为 **6.11.2**。安装包 `METADATA` 声明 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`，并说明另有商业许可渠道。四份元数据已原样保存在 `docs/licenses/*-METADATA.txt`；原件来自 `.venv/Lib/site-packages/*-6.11.2.dist-info/METADATA`。

包中 `licenses/LicenseRef-Qt-Commercial.txt` 只是针对已持有效商业许可者的条款引用，不表示本项目取得 Qt 商业授权。原文也已保存。当前使用 PySide6 开源发行包；Qt 自身及随附第三方组件的适用许可须按实际组件判断，不能仅用绑定包顶层声明概括全部 DLL。参考 [Qt 许可说明](https://doc.qt.io/qt-6/licensing.html)与 [Qt for Python 第三方许可](https://doc.qt.io/qtforpython-6/licenses.html)。

本界面主要使用 Qt Core、Gui、Widgets 和 SVG。下载保存的开源许可证原文为：

- `docs/licenses/LGPL-3.0.txt`，来源 [GNU LGPL v3](https://www.gnu.org/licenses/lgpl-3.0.txt)。
- `docs/licenses/GPL-3.0.txt`，来源 [GNU GPL v3](https://www.gnu.org/licenses/gpl-3.0.txt)。
- `docs/licenses/GPL-2.0.txt`，来源 [GNU GPL v2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt)。

下载 URL、获取时间和 SHA-256 均在 `docs/licenses/sources.json`。Qt/PySide 上游代码可从 [Qt 源码站](https://code.qt.io/)及 [PySide 项目仓库](https://code.qt.io/cgit/pyside/pyside-setup.git/)查阅。本项目未修改其库代码。当前程序以目录方式携带独立动态库。

PyInstaller 6.22.2 用于本地 Windows 打包；其随包 `COPYING.txt` 原样保存在 `docs/licenses/PyInstaller-COPYING.txt`，含 GPL 许可及对构建应用的例外，详见该原文和 [PyInstaller 许可说明](https://pyinstaller.org/en/stable/license.html)。开发和研究依赖的精确版本见 `uv.lock`；它们的许可随各安装包保留，研究工具不作为游戏核心依赖。

## Noto Sans SC 字体

字体文件为 `assets/fonts/NotoSansSC.ttf`，来自 [Google Fonts 的 Noto Sans SC 目录](https://github.com/google/fonts/tree/main/ofl/notosanssc)，下载清单及 SHA-256 见 `assets/fonts/sources.json`。

适用 SIL Open Font License 1.1，完整原文为 `assets/fonts/OFL.txt`。所下载许可文件的版权声明为 “Copyright 2014-2021 Adobe”，并列有保留字体名 Source。字体文件未做字形修改，保留该许可与声明。

## 维基文库史料

《明史》《明通鉴》《大明律》和《大明会典》古籍原作属于历史公版文本。维基文库现代转录、标点、整理及网页附加内容另有贡献者权利，页面通常采用 CC BY-SA 4.0，不能把整页现代贡献一概视作公版。

本项目保留原始网页或 Wikitext，提取正文，另行制作简体名称、索引、摘录、年代注记与结构化字段；这些是整理与转换。归属、页面 URL、下载时间、文件路径、摘要哈希和复用备注分别见：

- `data/history/sources_people_laws.json`，原始文件在 `data/history/raw/`。
- `data/history/sources_geography.json`，地理志存本在 `data/history/raw/geography/`。

来源网页及其历史页用于识别维基文库贡献者；转录摘录和相关整理保留来源及相同方式共享的适用条款。[CC BY-SA 4.0 许可](https://creativecommons.org/licenses/by-sa/4.0/)不自动覆盖本项目无关的原创游戏代码。每条结构化资料的 `source_ids` 可追溯到来源清单。

## Natural Earth 与 1580 年参考图

交互地图陆地轮廓和现代城市参考坐标来自 Natural Earth v5.1.2，按其 [官方使用条款](https://www.naturalearthdata.com/about/terms-of-use/)属于公版数据。原始文件为 `data/history/raw/geography/ne_110m_land.geojson` 和 `ne_10m_populated_places_simple.geojson`，条款存本为同目录 `natural_earth_terms.html`。派生 `data/history/map_land.geojson` 用于底图，城市点经选择和匹配用于参考定位；这不表示 Natural Earth 提供了明代历史边界。

单独的参考图 `data/history/raw/geography/ming_empire_1580_reference.svg` 来自 Wikimedia Commons 的 [Ming Empire cca 1580 (en)](https://commons.wikimedia.org/wiki/File:Ming_Empire_cca_1580_(en).svg)。地图作者 Michal Klajban（Podzemnik），SVG 衍生作者 Jann，其他贡献见文件历史。适用 **CC BY-SA 3.0 Czech Republic**，见[许可原文入口](https://creativecommons.org/licenses/by-sa/3.0/cz/deed.en)。本项目保留下载 SVG 原件，未改制其地理内容；元数据快照为 `data/history/raw/geography/commons_ming_map_api.json`，URL、哈希与说明见地理来源清单。

CHGIS 官网许可页已保存为 `data/history/raw/geography/chgis_v6_license.html`，仅作研究记录，未导入其地理数据库。CBDB 也未导入数据库。网页研究记录不表示取得数据库的其他复用权限。

## 随包位置

源码项目中以上路径相对项目根目录。Windows 目录式构建将 `data`、`assets`、`docs` 和本说明一起包含，通常位于 `MingImperialDesk/_internal/`；许可证下载与安装包元数据保存在其中的 `docs/licenses/`。完整文件清单以实际构建目录为准。
