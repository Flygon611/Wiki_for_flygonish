# 见远观星集

《青梅竹马失踪后变成电飞鼠这档事》与《想要飞的始祖小鸟》的设定维基。
Fandom / Wikia 2010 年代风格的静态站点 + 一套本地可视化编辑器。

站点内容包括角色、组织、地点、专有名词与剧情总结，带信息框、双向链接、
分类导航、站内搜索、剧透折叠和「未完成的页面」清单。

---

## 目录结构

```
.
├── content/                     ← 正文（Obsidian 风格 Markdown，改这里）
│   ├── 首页.md
│   ├── 青梅竹马失踪后变成电飞鼠这档事/
│   │   ├── _作品.json           ← 作品的标题、配色、分类顺序、代表条目
│   │   ├── 人物/*.md
│   │   ├── 组织/*.md
│   │   └── …
│   └── 想要飞的始祖小鸟/
├── assets/                      ← 图片（按作品分目录）
├── docs/                        ← 生成出来的静态站（GitHub Pages 发布这个目录）
├── editor/                      ← 本地编辑器
│   ├── serve.py                 ← 编辑器后端
│   └── ui/                      ← 编辑器前端
├── tools/
│   ├── import_obsidian.py       ← 从 Obsidian 库一次性导入
│   ├── check_site.py            ← 站点链接自检
│   ├── check_editor.py          ← 编辑器路径安全检查
│   └── make_buttons.py          ← 生成 88×31 小按钮站标
├── wikicore/                    ← 渲染器与主题（build.py 的内部模块）
├── build.py                     ← 生成器：content/ → docs/
└── wiki.config.json             ← 站点名、标语、配色、页脚、仓库地址
```

**只有 `content/` 和 `assets/` 是你的正文。** `docs/` 是生成物，随时可以整个删掉重建；
但发布用 GitHub Pages 时它是产物，所以要提交。

---

## 日常使用

### 只想改内容 → 用编辑器

```bash
python3 editor/serve.py
```

浏览器会自动打开 <http://127.0.0.1:8765/>。左边选页面，中间写 Markdown，
右边实时预览。改完 **保存（⌘S / Ctrl+S）**，会自动重新构建站点。

编辑器里能做的事：

| 位置 | 功能 |
| --- | --- |
| 左栏 | 页面树（按作品 › 分类）、筛选、**＋ 新建**（带人物/组织/地点等模板） |
| 中栏工具栏 | 标题、粗体、`[[双链]]`、外链、图片、信息框、提示框、🔒 剧透节、表格、frontmatter |
| 预览 | 用生成器同一套渲染器，所见即所得；点链接会用新标签页打开已构建的页面 |
| 信息框 | 把 `> [!info]` 文本块解析成**表单**，改完点「写回正文」，不用手动对齐格式 |
| 图片 | 拖拽上传 / 粘贴截图上传，点一下就插入 `![[文件名\|150]]` |
| Git | 看改动、写提交说明、提交、提交并推送、拉取；还有上次构建的日志 |
| 站点设置 | 直接编辑 `wiki.config.json` 和每部作品的 `_作品.json`（JSON 写错会拒绝保存） |

常用快捷键：`⌘S` 保存 · `⌘B` 粗体 · `⌘I` 斜体 · 输入 `[[` 弹双链补全
（↑↓ 选择，Enter 确认）· 输入 `![[` 弹图片补全。

### 不想开编辑器 → 命令行

```bash
python3 build.py            # 生成到 docs/
python3 build.py --open     # 生成后起本地预览并开浏览器
python3 tools/check_site.py # 自检：链接、图片、样式是否都存在
```

只需要 **Python 3.8+**，没有任何第三方依赖，不用 `pip install`、不用 `npm install`。
---

## 换成自己的内容

### 改站点名 / 标语 / 页脚

直接编辑 `wiki.config.json`，或者用编辑器的「站点设置」。主要字段：

| 字段 | 说明 |
| --- | --- |
| `site_name` | 站名（页头和页脚显示） |
| `site_tagline` | 副标题 |
| `about` | 左栏「关于」框的文字 |
| `footer` | 页脚，支持 HTML（已经写好 CC 授权与版权行） |
| `theme` | 站点主色。`accent` / `accent2` / `accent3` 是一组渐变 |
| `logo` | 页头左上角的小图，放在 `assets/` 下（现在是 `logo.jpg`） |
| `icon` | 浏览器标签页图标（现在是 `favicon.png`，取自博客的像素标） |
| `apple_icon` | iOS 加到主屏幕时的图标（180×180） |
| `og_image` | 分享链接时的缩略图，建议 1200×630（现在是 `og-cover.png`） |
| `site_url` | 站点正式地址。`og:image` 和 `canonical` 需要绝对路径，靠它拼 |
| `buttons` | 页脚那排 88×31 小按钮的清单（图片、说明、链接） |
| `repo.url` | 仓库地址，决定条目右上角「编辑 / 历史」按钮指向哪 |
| `spoiler.fold_headings` | 命中这些关键词的小节默认折叠（现在是第二季、第三季、番外等） |
| `soft_breaks` | 单换行怎么处理：`br`（默认，按你笔记里的换行）/ `space`（合并成一段） |

### 加一部新作品

在 `content/` 下新建一个文件夹，放一个 `_作品.json`：

```json
{
  "title": "作品全名",
  "nav_label": "顶部导航上的短名",
  "tagline": "一句话简介",
  "description": "作品门户页上的介绍",
  "accent": "#8a4f9e",
  "order": 3,
  "category_order": ["人物", "地点"],
  "featured": ["某个页面名"]
}
```

然后建分类子文件夹、往里放 `.md` 就行。`accent` 一改，那部作品的所有页面
（页头渐变、信息框配色、链接色）都会跟着换成这个色。

### 首页与顶层页面

`content/首页.md` 是站点首页。如果在 `content/` 根目录下再放别的 `.md`
（比如一个「总览」页），它会生成到站点根目录（`docs/总览.html`），
并出现在「所有页面」和搜索里 —— 编辑器的「新建页面」里选
「（根目录 · 总览类页面）」就是这个效果。

注意：首页只能有一个。同时存在 `content/首页.md` 和 `content/index.md` 时构建会直接报错。

### 图标素材与授权

侧栏那几个像素图标来自 [pixelarticons](https://github.com/halfmage/pixelarticons)（**MIT**），
放在 `assets/icons/`，同目录有 `README.txt` 记着出处。要换图标：把 SVG 丢进那个目录，
再改 `build.py` 的 `make_sidebar()` 里各盒子挂的 `"icon": "xxx.svg"`。

> 图标是**内联**进 HTML 的（不是 `<img>`），因为 SVG 用的是 `fill="currentColor"`，
> 只有内联才能跟着主题配色变。文件里的 `width`/`height` 会被去掉，尺寸交给 CSS 的 `.pk` 控制。

用别的图标库时留意授权，常见几种：

| 库 | 授权 | 能不能打包进公开仓库 |
| --- | --- | --- |
| Kenney | CC0 | ✅ 可以，连署名都不用 |
| pixelarticons | MIT | ✅ 可以，保留授权声明 |
| Fugue Icons | CC BY 3.0 | ✅ 可以，需要署名 |
| ICOOON MONO | 免费商用、免署名 | ❌ **禁止再分发**，只能直接在页面里用 |
| FamFamFam Silk | 原为 CC BY 2.5 | ⚠️ 官网已挂，现有镜像多数没写授权 |

站上的[小按钮与素材](content/小按钮.md)那一页有更完整的清单。

### 页脚的 88×31 小按钮

`assets/buttons/` 里是那个年代的站标。要改文字或配色，编辑
`tools/make_buttons.py` 顶部那张 `BUTTONS` 表，然后重跑：

```bash
python3 tools/make_buttons.py
```

生成的按钮要出现在页脚，就在 `wiki.config.json` 的 `buttons` 数组里加一条
（`href` 写站内路径；外链加 `"ext": true`）。

站上有一页 [小按钮与素材](content/小按钮.md)，写着交换链接的代码、
素材来源和各自的授权情况，可以照抄给别人。

### 分类

**分类就是子文件夹名。** `人物/上鹈.md` → 分类「人物」。
支持一层嵌套：`地点/岛屿/盐风镇.md` → 「地点 › 岛屿」，
父分类页会自动汇总子分类。分类页、侧栏计数、分类条都是自动生成的。

---

## Markdown 语法

内容按 **Obsidian 格式** 写，生成器直接认：

| 写法 | 效果 |
| --- | --- |
| `[[页面名]]` / `[[页面名\|显示文字]]` | 站内链接。目标不存在时自动变成**红色链接** |
| `![[图片.jpg\|150]]` | 插入图片，`150` 是宽度。**按文件名在全站找**，大小写不敏感 |
| `> [!info] 标题` + `> - **字段**：值` | 右侧信息框（有字段行或图片才算信息框） |
| `> [!tip]` `[!warning]` `[!danger]` `[!quote]` … | 彩色提示框 |
| `**粗体**` `*斜体*` `~~删除线~~` `==高亮==` `` `代码` `` | 行内样式 |
| `## 标题` `### 标题` | 章节，自动生成目录和锚点 |
| ` ```代码``` ` | 围栏代码块，内部原样显示、不做 Markdown 解析 |
| `%%注释%%` | 会被丢掉（只写给自己看的内容） |
| 原生 `<table>` `<div>` `<figure>` `<img src="x.jpg">` | 原样保留；`<img>` 也按文件名自动找图并改对路径 |

页面开头还可以写可选的 frontmatter：

```markdown
---
标题: 显示用的页面标题      # 不写就用文件名
标签: [复原团, 主角]        # 会出现在页面底部的分类条，并生成标签页
别名: [另一个常见的叫法]    # 用别的名字也能链接到这个页面
剧透: true                  # 强制在这一页顶部显示剧透横幅
---
```

**剧透折叠**：标题里含「第二季」「第三季」「番外」「1.5」等关键词的小节，
会自动被包进默认收起的折叠块，目录里标 🔒，展开状态浏览器会记住。

---

## 发布到 GitHub Pages

仓库地址已经配好（`wiki.config.json` 里的 `repo.url`）：`Flygon611/Wiki_for_flygonish`。

**首次推送：**

```bash
cd /Users/nijiboshi06/Documents/deepseek-harness/DSH_Others/nijiboshi-wiki
git add -A
git commit -m "初始化维基"
git branch -M main
git remote add origin https://github.com/Flygon611/Wiki_for_flygonish.git
git push -u origin main
```

（如果提示要密码：GitHub 不接受账号密码，需要在
[Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
生成一个有 `repo` 权限的 token，粘贴在密码位置。macOS 的钥匙串会记住它，
之后编辑器里的「推送」按钮就能直接用。）

**然后开启 Pages（只需做一次）：**

1. 打开仓库 → **Settings** → 左侧 **Pages**
2. **Source** 选 `Deploy from a branch`
3. **Branch** 选 `main`，目录选 **`/docs`** → Save
4. 等一两分钟，站点在 `https://flygon611.github.io/Wiki_for_flygonish/`

**以后更新：** 编辑器里点「提交并推送」，或在命令行 `python3 build.py && git add -A && git commit -m "更新" && git push`。
推送后 Pages 会自动重新发布，一两分钟生效。

> 为什么是 `docs/` 目录：这样完全不需要 GitHub Actions 权限，
> 免费账号 + 公开仓库就能用。私有仓库的 Pages 需要 GitHub Pro（免费账号不支持），
> 如果哪天想把仓库设成私有，可以改用 Cloudflare Pages / Vercel，两者都支持私有仓库免费发布。

---

## 内容来源与现状

内容最初从 `/Users/nijiboshi06/Desktop/工具/Obsidian` 导入（见 `content/.import-manifest.json`，
记录了每个页面的来源路径与导入时的哈希）。导入是一次性的：**现在以仓库里的 `content/` 为准**，
Obsidian 那边之后怎么改都不会自动同步过来。要重新导入：

```bash
python3 tools/import_obsidian.py           # 先预览，不写文件
python3 tools/import_obsidian.py --write   # 真的导入（已存在的页面默认跳过，加 --force 覆盖）
```

当前状态：

- 39 个页面（38 个条目 + 首页），60 张图片
- 4 篇空笔记已生成占位页：**来自帕底亚地区的一封信、冻、蒲子、幼驯染失踪后变成宝可梦这档事2**
- **8 个红色链接**（被引用但还没建的条目）：
  `三元山`、`天顶山`、`瀑布之森`、`幼失鼠3`、`语海`、`轮回`、`重叠`、`帕底亚三人组`
  —— 全部列在站点的[未完成的页面]里，编辑器里新建同名页面即可自动接上
- 第一部作品按博客的叫法命名为《青梅竹马失踪后变成电飞鼠这档事》，
  原库里的《幼驯染失踪后变成宝可梦这档事》记在 `_作品.json` 的 `aka` 字段里，门户页显示「又名」

---

## 已知限制

- **目录里有中文**：URL 会百分号编码（浏览器地址栏看着乱，但正常访问）。
  GitHub Pages 能正确处理，链接自检也通过。
- **改页面文件名不会自动更新引用**。重命名后请用 `tools/check_site.py` 看看有没有新增红色链接。
- **`最近更新`按源文件修改时间排序**，构建时记录下来。另一台机器 clone 下来时间戳会变，
  重新构建一次即可。
- **编辑器没有登录验证**，只监听 `127.0.0.1`，不要改成 `0.0.0.0` 暴露到局域网/公网。
  所有来自浏览器的路径参数都做了白名单式校验（`python3 tools/check_editor.py` 覆盖了这组检查）。
- **不要直接双击 `docs/index.html` 看**：浏览器在 `file://` 下不允许网页读取 `search.json`，
  搜索会失效（页面会给出提示）。本地看请用 `python3 build.py --open`，或发布后用线上地址。
- **删除页面**是移到 `content/.trash/`（该目录已被 git 忽略），不会真删；要恢复就手动移回来。
- **分享缩略图要用绝对地址**：`og_image` 依赖 `wiki.config.json` 里的 `site_url`。
  换域名（比如以后绑自定义域名）记得同步改它，否则链接卡片的图会指向老地址。
- **`check_site.py` 还会检查标签配平**。如果你在正文里手写 `<div>`／`<table>` 之类的 HTML
  却忘了闭合，它会报出行号 —— 这是内容里的笔误，不是生成器的问题，按提示补上闭合标签即可。
- **顶层页面不能和站点自带页面同名**：`content/all.md`、`search.md`、`404.html`、`index.md`
  之类会让构建直接报错并指名冲突（否则你的页面会被特殊页面悄悄覆盖）。
- **标签名归一化后如果撞车**（例如同时有 `a/b` 和 `a_b`），构建会自动加短后缀区分，
  并在输出里提示；`index` 这种保留名也会自动让开。

---

## 命令速查

```bash
python3 editor/serve.py                 # 启动编辑器（8765 端口）
python3 editor/serve.py --port 9000     # 换端口
python3 build.py                        # 构建站点
python3 build.py --open                 # 构建并预览
python3 tools/check_site.py             # 站点自检：静态链接 + 搜索候选链接
python3 tools/check_site.py --list      # 顺带列出所有页面
python3 tools/check_editor.py           # 编辑器路径安全检查
```

---

## 授权

本站所有原创内容采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 授权，
Copyright © 虹星 版权所有。

《宝可梦》系列的名称与官方设定版权归任天堂 / GAME FREAK / Creatures Inc. 所有。
