# -*- coding: utf-8 -*-
"""页面外壳与主题（Fandom/Wikia 2010 风格）。"""

import datetime
import html as _html
import os
import re

# 图标目录（由 build.py 在构建时指过来），见 assets/icons/
ICON_DIR = None
_icon_cache = {}


def icon(name, base="", size=16, cls="pk"):
    """站内小图标。

    PNG 用 <img>，SVG 走内联（SVG 里是 fill="currentColor"，用 <img> 就丢了颜色）。

    尺寸一定写在 width/height 属性上，不能只靠 CSS：之前只靠 CSS，
    结果用户浏览器缓存了旧的样式表、HTML 却是新的，内联 SVG 没有宽高就撑满了整个侧栏。
    """
    if not name:
        return ""
    if os.path.splitext(name)[1].lower() == ".svg":
        key = ("svg", name, cls, size)
        if key in _icon_cache:
            return _icon_cache[key]
        out = ""
        path = os.path.join(ICON_DIR or "", name)
        if ICON_DIR and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    out = f.read().strip()
                out = out.replace("<svg ", '<svg class="%s" width="%d" height="%d" '
                                         % (cls, size, size), 1)
                out = re.sub(r'\s(?:width|height)="[^"]*"', "", out)
            except OSError:
                out = ""
        _icon_cache[key] = out
        return out
    return ('<img class="%s" src="%sassets/icons/%s" width="%d" height="%d" alt="">'
            % (cls, base, _html.escape(name, quote=True), size, size))


FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="12" fill="#2a4f78"/>'
    '<path d="M32 12c9 0 16 6 16 15 0 11-8 20-16 25-8-5-16-14-16-25 0-9 7-15 16-15z" fill="#8ecf6a"/>'
    '<circle cx="25" cy="27" r="3.4" fill="#14314f"/><circle cx="39" cy="27" r="3.4" fill="#14314f"/>'
    '<path d="M24 38c5 4 11 4 16 0" stroke="#14314f" stroke-width="2.6" fill="none" stroke-linecap="round"/>'
    "</svg>"
)

THEME_CSS = r"""
:root{
  --accent:{{accent}}; --accent-2:{{accent2}}; --accent-3:{{accent3}};
  --link:{{link}}; --link-visited:{{link_visited}}; --red:{{red}};
  --page-bg:{{page_bg}}; --content-bg:#fff;
  --border:{{border}}; --border-soft:{{border_soft}};
  --box-head-a:{{box_head_a}}; --box-head-b:{{box_head_b}};
  --text:#1b1b1b; --muted:#616b73; --mark:{{mark}};
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--page-bg); color:var(--text);
  font:13px/1.75 "Helvetica Neue",Helvetica,Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
}
a{color:var(--link); text-decoration:none}
a:hover{text-decoration:underline}
a:visited{color:var(--link-visited)}
a.new{color:var(--red)}
a.ext:after{content:"\2197"; font-size:10px; margin-left:1px; color:#7b8794}
img{max-width:100%}

/* ---------------------------------------------------- 顶部条 */
.top-bar{background:#20262d; border-bottom:1px solid #14181d}
.top-inner{max-width:1260px; margin:0 auto; padding:7px 16px; display:flex; align-items:center; gap:10px}
.global-brand{color:#c9d3dd; font-size:12px; letter-spacing:.5px; white-space:nowrap}
.global-brand b{color:#fff}
.top-links{margin-left:auto; display:flex; gap:14px; font-size:12px}
.top-links a{color:#b9c5d1}
.top-links a:hover{color:#fff; text-decoration:none}

/* ---------------------------------------------------- 站点头 */
.site-header{background:linear-gradient(180deg,var(--accent-3) 0%,var(--accent) 45%,var(--accent-2) 100%); border-bottom:3px solid var(--accent-2)}
.site-header-inner{max-width:1260px; margin:0 auto; padding:14px 16px 12px; display:flex; align-items:center; gap:14px}
.logo-box{width:52px; height:52px; flex:0 0 52px; border-radius:8px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.4);
  display:flex; align-items:center; justify-content:center; overflow:hidden}
.logo-box img{width:100%; height:100%; object-fit:cover}
.logo-box svg{width:100%; height:100%}
.site-id{min-width:0}
.site-name{display:block; color:#fff; font-size:26px; line-height:1.2; font-weight:700;
  text-shadow:1px 1px 0 rgba(0,0,0,.35); font-family:Georgia,"Songti SC","STSong",serif}
.site-name:hover{text-decoration:none}
.site-tagline{display:block; color:#dce8f4; font-size:12px; margin-top:2px; text-shadow:1px 1px 0 rgba(0,0,0,.25)}
.header-right{margin-left:auto; display:flex; align-items:center; gap:10px}
.search-form{position:relative; display:flex; background:#fff; border:1px solid var(--accent-2); border-radius:3px; overflow:visible}
.search-form input{border:0; outline:0; padding:6px 8px; width:210px; font-size:13px; background:transparent}
.search-form button{border:0; background:var(--accent-2); color:#fff; padding:0 12px; cursor:pointer; font-size:13px}
.search-form button:hover{background:var(--accent)}
.search-results{position:absolute; top:32px; left:0; right:0; background:#fff; border:1px solid var(--border);
  box-shadow:0 3px 10px rgba(0,0,0,.25); z-index:50; display:none; max-height:340px; overflow:auto}
.search-results.on{display:block}
.search-results a{display:block; padding:6px 9px; border-bottom:1px solid var(--border-soft); font-size:13px}
.search-results a:hover{background:#eef4fa; text-decoration:none}
.search-results .sr-cat{color:var(--muted); font-size:11px; margin-left:4px}
.search-results .sr-none{padding:8px 9px; color:var(--muted); font-size:12px}
.hit-count{color:var(--muted); font-size:12px}

/* ---------------------------------------------------- 横向导览 */
.nav-bar{background:linear-gradient(180deg,#fdfefe,#e9eff5); border-bottom:1px solid var(--border)}
.nav-inner{max-width:1260px; margin:0 auto; padding:0 16px; display:flex; flex-wrap:wrap; align-items:stretch}
.nav-inner>a{padding:9px 13px; font-size:13px; color:#22456e; border-right:1px solid var(--border-soft); font-weight:600}
.nav-inner>a:first-child{border-left:1px solid var(--border-soft)}
.nav-inner>a:hover{background:#fff; text-decoration:none}
.nav-inner>a.on{background:var(--accent); color:#fff}

/* ---------------------------------------------------- 布局 */
.layout{max-width:1260px; margin:14px auto 0; padding:0 16px; display:flex; gap:16px; align-items:flex-start}
.sidebar{width:186px; flex:0 0 186px}
.content{flex:1 1 auto; min-width:0}
.box{background:var(--content-bg); border:1px solid var(--border); border-radius:3px; margin-bottom:12px; overflow:hidden}
.box-title{background:linear-gradient(180deg,var(--box-head-a),var(--box-head-b)); border-bottom:1px solid var(--border);
  padding:5px 9px; font-size:12px; font-weight:700; color:#22456e; letter-spacing:.4px}
.box ul{list-style:none; margin:0; padding:6px 0}
.box li{padding:0}
.box li a{display:block; padding:3px 9px 3px 12px; font-size:12.5px; border-left:3px solid transparent}
.box li a:hover{background:#eef4fa; border-left-color:var(--accent); text-decoration:none}
.box li.on a{background:#e6eef6; border-left-color:var(--accent); font-weight:700}
.box li a .cnt{color:var(--muted); font-size:11px; float:right}
.box .box-body{padding:8px 9px; font-size:12px; color:#333}
.box .sub{padding:4px 9px 2px 9px; font-size:11px; color:var(--muted); font-weight:700; letter-spacing:.5px}
/* 内联像素图标（来自 assets/icons/） */
/* 尺寸由 width/height 属性决定，这里只管对齐、间距与透明感 */
.pk{flex:0 0 auto; vertical-align:-3px; margin-right:5px; border:0; opacity:.88}
.pk.pk-lg{vertical-align:-4px; margin-right:6px; opacity:1}
.sidebar .work-block{border-top:1px solid var(--border-soft)}
.sidebar .work-title{display:block; padding:6px 9px; font-weight:700; font-size:12.5px; color:var(--accent-2)}
.sidebar .work-title:hover{text-decoration:none; background:#eef4fa}

/* ---------------------------------------------------- 内容区 */
.page-tabs{display:flex; align-items:flex-end; gap:2px; margin-bottom:-1px; padding-left:6px}
.page-tabs .tab{padding:5px 14px; font-size:12.5px; background:#e3eaf1; border:1px solid var(--border);
  border-bottom:0; border-radius:3px 3px 0 0; color:#31536f}
.page-tabs .tab.active{background:#fff; font-weight:700; color:var(--text); padding-bottom:6px}
.page-tabs .tab.disabled{color:#98a4ae; cursor:not-allowed}
.page-tabs .tab.spacer{background:transparent; border:0; flex:1}
.page-tabs a.tab:hover{background:#fff; text-decoration:none}
.article-wrap{background:var(--content-bg); border:1px solid var(--border); border-radius:0 3px 3px 3px;
  box-shadow:0 1px 2px rgba(0,0,0,.06); padding:16px 20px 20px}
h1.page-title{margin:0 0 2px; font-size:25px; line-height:1.3; font-weight:700;
  font-family:Georgia,"Songti SC","STSong",serif; border-bottom:1px solid var(--border); padding-bottom:6px}
.page-subtitle{color:var(--muted); font-size:11.5px; margin:6px 0 14px}
.page-subtitle .sep{margin:0 6px; color:#c3ccd4}

.article h2{font-size:19px; margin:24px 0 10px; padding-bottom:4px; border-bottom:1px solid var(--border);
  font-family:Georgia,"Songti SC","STSong",serif}
.article h3{font-size:16px; margin:20px 0 8px}
.article h4{font-size:14px; margin:16px 0 6px}
.article p{margin:9px 0}
.article ul,.article ol{margin:9px 0 9px 0; padding-left:26px}
.article li{margin:3px 0}
.article hr{border:0; border-top:1px solid var(--border-soft); margin:16px 0}
.article blockquote{margin:10px 0; padding:6px 12px; border-left:4px solid var(--border); background:#f7fafc; color:#333}
.article code{background:#f2f5f7; border:1px solid var(--border-soft); border-radius:2px; padding:0 4px;
  font-family:"SF Mono",Menlo,Consolas,monospace; font-size:12px}
/* 围栏代码块 ``` */
.article pre.codeblock{background:#1f2731; color:#d8e4ef; border:1px solid #16202a; border-radius:3px;
  padding:10px 13px; overflow:auto; margin:12px 0;
  font:12px/1.7 "SF Mono",Menlo,Consolas,"PingFang SC",monospace}
.article pre.codeblock code{background:transparent; border:0; padding:0; color:inherit; font-size:inherit;
  font-family:inherit}
.article mark{background:var(--mark); padding:0 2px}
.anchor{opacity:0; margin-left:6px; font-size:12px}
.anchor a{color:#9fb0be}
h2:hover .anchor,h3:hover .anchor{opacity:1}
.wikimg{border:1px solid var(--border-soft); background:#fff; padding:2px; height:auto}
.center-img{text-align:center}

.wikitable{border-collapse:collapse; margin:12px 0; font-size:12.5px; background:#fff; max-width:100%}
.wikitable th,.wikitable td{border:1px solid var(--border); padding:5px 9px; text-align:left; vertical-align:top}
/* 只让「表头行」不折行。正文单元格有时也用 <th>（作者手写的表格），
   对它们也 nowrap 会让宽表格冲出内容区。 */
.wikitable thead th,.article table:not(.wikitable) tr:first-child th{white-space:nowrap}
.article table:not(.wikitable) th,.article table:not(.wikitable) td{word-break:break-word}
.wikitable thead th{background:linear-gradient(180deg,var(--box-head-a),var(--box-head-b)); color:#22456e}
.article table:not(.wikitable):not(.infobox-table){border-collapse:collapse; margin:12px 0; font-size:12.5px}
.article table:not(.wikitable):not(.infobox-table) th,
.article table:not(.wikitable):not(.infobox-table) td{border:1px solid var(--border); padding:5px 9px; vertical-align:top; text-align:left}
.article table:not(.wikitable):not(.infobox-table) th{background:linear-gradient(180deg,var(--box-head-a),var(--box-head-b))}

/* ---------------------------------------------------- 信息框 */
.infobox{float:right; width:300px; margin:0 0 14px 18px; border:1px solid var(--border); border-radius:3px;
  background:#fbfdff; font-size:12px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.08)}
.infobox-title{background:linear-gradient(180deg,var(--accent-3),var(--accent) 55%,var(--accent-2));
  color:#fff; font-weight:700; text-align:center; padding:7px 8px; font-size:14px;
  text-shadow:1px 1px 0 rgba(0,0,0,.3); font-family:Georgia,"Songti SC","STSong",serif}
.infobox-image{text-align:center; padding:8px; background:#fff; border-bottom:1px solid var(--border-soft)}
.infobox-image img{border:1px solid var(--border-soft); padding:2px; background:#fff; height:auto}
.infobox-table{width:100%; border-collapse:collapse}
.infobox-table th{width:1%; white-space:nowrap; text-align:left; font-weight:700; color:#22456e;
  background:#eaf2f9; padding:4px 7px; border-top:1px solid var(--border-soft); vertical-align:top}
.infobox-table td{padding:4px 7px; border-top:1px solid var(--border-soft); vertical-align:top; word-break:break-word}
.infobox-extra{padding:7px 8px; border-top:1px solid var(--border-soft); background:#fff; font-size:12px}
.infobox-extra p{margin:4px 0}

/* ---------------------------------------------------- callout */
.callout{margin:12px 0; border:1px solid var(--border); border-left:5px solid var(--accent); border-radius:3px;
  background:#f7fafd; padding:7px 12px}
.callout-title{font-weight:700; margin-bottom:3px; color:#22456e}
.callout-title .callout-label{background:var(--accent); color:#fff; font-size:11px; border-radius:2px; padding:1px 6px; margin-right:5px}
.callout-body>p:first-child{margin-top:4px}
.callout-body>p:last-child{margin-bottom:2px}
.c-tip{border-left-color:#4a9e5c; background:#f4fbf5}.c-tip .callout-label{background:#4a9e5c}.c-tip .callout-title{color:#2f6b3c}
.c-warning{border-left-color:#d9a02b; background:#fdf9ef}.c-warning .callout-label{background:#d9a02b}.c-warning .callout-title{color:#8a6415}
.c-danger,.c-fail{border-left-color:#c0392b; background:#fdf4f3}.c-danger .callout-label,.c-fail .callout-label{background:#c0392b}
.c-danger .callout-title,.c-fail .callout-title{color:#8f2b20}
.c-success{border-left-color:#3f8f57; background:#f4fbf5}.c-success .callout-label{background:#3f8f57}
.c-question{border-left-color:#7a5cc0; background:#f8f5fd}.c-question .callout-label{background:#7a5cc0}
.c-quote{border-left-color:#8a97a3; background:#f8f9fa}.c-quote .callout-label{background:#8a97a3}
.c-example{border-left-color:#2a7f9e; background:#f4fafc}.c-example .callout-label{background:#2a7f9e}
.c-note .callout-label{background:#5a7f9e}.c-note{border-left-color:#5a7f9e}

/* ---------------------------------------------------- 剧透 */
.spoiler-banner{border:1px solid #e0c060; border-left:6px solid #e0a800; background:#fffaf0; border-radius:3px;
  padding:9px 13px; margin:0 0 15px; font-size:12.5px; color:#6b5312}
.spoiler-banner b{color:#8a5a00}
.spoiler-banner .dismiss{float:right; color:#a8912f; cursor:pointer; font-size:12px}
.spoiler-fold{border:1px dashed #d8c07a; background:#fffdf6; border-radius:3px; margin:14px 0; padding:0}
.spoiler-fold>summary{cursor:pointer; padding:8px 12px; font-weight:700; color:#8a6d1f; font-size:13px; list-style:none}
.spoiler-fold>summary::-webkit-details-marker{display:none}
.spoiler-fold>summary:before{content:"\25B6"; display:inline-block; margin-right:7px; font-size:10px; transition:transform .15s}
.spoiler-fold[open]>summary:before{transform:rotate(90deg)}
.spoiler-fold[open]>summary{border-bottom:1px solid #efe2bd}
.spoiler-fold .spoiler-body{padding:2px 14px 10px}
.spoiler-fold h2,.spoiler-fold h3{margin-top:12px}

/* ---------------------------------------------------- 目录 / 页脚块 */
.toc{display:inline-block; min-width:260px; max-width:100%; background:#f8fafc; border:1px solid var(--border);
  border-radius:3px; padding:8px 14px 10px; margin:6px 0 16px; font-size:12.5px}
.toc-head{font-weight:700; color:#22456e; margin-bottom:4px; display:flex; align-items:center; gap:8px}
.toc-head .toggle{cursor:pointer; color:var(--link); font-weight:400; font-size:11.5px}
.toc ol{margin:0 0 0 4px; padding-left:18px}
.toc ol ol{margin:2px 0}
.toc li{margin:1px 0}
.toc .lock{color:#a8912f; font-size:11px}
.catlinks{margin-top:22px; padding:6px 10px; background:#f4f8fb; border:1px solid var(--border); border-radius:3px;
  font-size:12px; color:var(--muted); clear:both}
.catlinks a{margin-right:2px}
.backlinks{margin-top:14px; background:#fbfcfd; border:1px solid var(--border-soft); border-radius:3px; padding:8px 12px; font-size:12.5px}
.backlinks .bl-title{font-weight:700; color:#22456e; margin-bottom:3px; font-size:12px}
.missing-media{color:var(--red); font-size:12px; border:1px dashed var(--red); padding:1px 5px; border-radius:2px}
.stub-notice{border:1px solid #cbd8e4; background:#f7fafd; border-radius:3px; padding:8px 12px; margin:0 0 14px; font-size:12.5px; color:#3f5a72}

/* ---------------------------------------------------- 未公开作品的密码门 */
.gate-box{border:1px solid var(--border); background:linear-gradient(180deg,#fdfefe,#f6f9fc);
  border-radius:3px; padding:14px 16px; margin:0 0 14px; max-width:540px}
.gate-title{font-size:15px; font-weight:700; color:#22456e; margin-bottom:6px}
.gate-hint{margin:0 0 10px; color:#3f5a72; font-size:12.5px}
.gate-box form{display:flex; align-items:center; gap:6px; flex-wrap:wrap}
.gate-box input[type=password]{border:1px solid var(--border); border-radius:3px; padding:5px 8px;
  font-size:13px; width:200px; background:#fff; outline:0}
.gate-box input[type=password]:focus{border-color:var(--accent)}
.gate-box button{border:1px solid var(--accent-2); background:var(--accent); color:#fff;
  border-radius:3px; padding:5px 16px; font-size:13px; cursor:pointer}
.gate-box button:hover{background:var(--accent-2)}
.gate-msg{color:var(--red); font-size:12.5px; margin:8px 0 0}
.gate-msg:empty{margin:0}
.gate-box noscript{display:block; margin-top:8px; color:#8f2b20; font-size:12.5px}
.gate-content{margin-top:2px}

/* ---------------------------------------------------- 列表页 / 卡片 */
.list-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:12px; margin:14px 0}
.card{border:1px solid var(--border); border-radius:3px; background:linear-gradient(180deg,#fdfefe,#f4f8fb); padding:10px 12px}
.card h4{margin:0 0 4px; font-size:14px}
.card h4 a{font-weight:700}
.card p{margin:0; color:var(--muted); font-size:12px; line-height:1.6}
.portal-hero{border:1px solid var(--border); border-radius:3px; overflow:hidden; margin-bottom:16px}
.portal-hero .ph-top{padding:14px 18px; background:linear-gradient(180deg,var(--accent-3),var(--accent) 55%,var(--accent-2)); color:#fff}
.portal-hero .ph-top h2{margin:0; border:0; color:#fff; font-size:22px; font-family:Georgia,"Songti SC",serif}
.portal-hero .ph-top p{margin:6px 0 0; color:#e6f0f8; font-size:12.5px}
.portal-hero .ph-body{padding:12px 18px; background:#fff}
.cat-block{margin-bottom:18px}
.cat-block h3{margin:0 0 6px; font-size:15px; border-bottom:1px solid var(--border-soft); padding-bottom:3px}
.chip{display:inline-block; border:1px solid var(--border); background:#f2f7fb; border-radius:11px;
  padding:1px 10px; margin:0 5px 5px 0; font-size:12.5px}
.chip:hover{background:#e4eef7; text-decoration:none}
.pagelist{columns:2; column-gap:26px; margin:12px 0}
.pagelist a{display:block; padding:2px 0; break-inside:avoid}
.recent-row{display:flex; gap:10px; padding:5px 0; border-bottom:1px solid var(--border-soft); font-size:12.5px}
.recent-row .when{color:var(--muted); flex:0 0 132px; font-variant-numeric:tabular-nums}
.recent-row .who{color:var(--muted); flex:0 0 120px}

/* ---------------------------------------------------- 页脚 */
.site-footer{margin:22px auto 0; max-width:1260px; padding:14px 16px 30px; color:var(--muted); font-size:11.5px; text-align:center}
/* 88x31 小按钮（2010 年代那一套站标） */
.sbtn-row{display:flex; flex-wrap:wrap; gap:5px; justify-content:center; margin:0 0 14px}
.sbtn{display:inline-block; line-height:0; text-decoration:none}
.sbtn img{display:block; border:0; image-rendering:pixelated}
.sbtn:hover img{outline:1px solid var(--accent); outline-offset:1px}
.site-footer .credit{margin-top:4px; font-size:11px; color:#8a949e}

/* ---------------------------------------------------- 条目状态横幅（mbox） */
.mbox{border:1px solid #a8c4e8; background:#eaf3fb; border-radius:3px; padding:7px 12px;
  margin:0 0 14px; font-size:12.5px; color:#24466b; display:flex; gap:9px; align-items:flex-start;
  clear:both; overflow:hidden}
.mbox .mbox-icon{flex:0 0 auto; margin-top:1px}
.mbox b{font-weight:700}
.mbox-content{background:#eaf3fb; border-color:#a8c4e8; color:#24466b}
.mbox-clean{background:#fdf6e3; border-color:#e0c060; color:#7a5c10}
.mbox-warn{background:#fdf1ef; border-color:#e0a79c; color:#8f2b20}
.mbox-ok{background:#f0f8f1; border-color:#a9d3b0; color:#2f6b3c}
/* MediaWiki 那种章节旁的 [编辑] */
.article h2 .editsection,.article h3 .editsection{float:right; font-size:11px; font-weight:400;
  font-family:"Helvetica Neue",Arial,sans-serif; color:var(--muted); margin-left:8px}
.article h2 .editsection a,.article h3 .editsection a{color:var(--link)}

/* ---------------------------------------------------- 词条导航盒（navbox） */
.navbox{border:1px solid #a8c4e8; border-radius:3px; background:#f7fbff; margin:18px 0 0;
  font-size:12.5px; clear:both}
.navbox-head{display:flex; align-items:center; gap:8px; padding:4px 9px;
  background:linear-gradient(180deg,#e2eefc,#b9d3f2); border-bottom:1px solid #a8c4e8}
.navbox-head .nb-links{flex:0 0 auto; font-size:11.5px; color:#33507a; min-width:3.5em}
.navbox-head .nb-links a{color:#0b5fa5}
.navbox-head .nb-title{flex:1 1 auto; text-align:center; font-weight:700; color:#24466b; font-size:13px}
.navbox-head .nb-toggle{flex:0 0 auto; cursor:pointer; color:#0b5fa5; font-size:11.5px;
  user-select:none; min-width:3.5em; text-align:right}
.navbox-head .nb-toggle:hover{text-decoration:underline}
.navbox-table{width:100%; border-collapse:collapse}
.navbox-table th,.navbox-table td{border:1px solid #cfe0f5; padding:4px 9px; vertical-align:middle}
.navbox-table .nb-group{background:#dbe9fb; color:#24466b; font-weight:700; text-align:center;
  width:5.2em; white-space:nowrap}
.navbox-table .nb-sub{background:#eef5fd; color:#33507a; font-weight:700; text-align:center;
  width:7em; white-space:nowrap}
.navbox-table .nb-list{background:#fff; text-align:left; line-height:2}
.navbox-table .nb-list a:hover{text-decoration:underline}
.navbox .nb-sep{color:#9db4cc; margin:0 5px}
.navbox .nb-missing{color:var(--red)}
.navbox.collapsed .navbox-table{display:none}
.navbox.collapsed .navbox-head{border-bottom:0}
.site-footer .fbrand{color:var(--accent-2); font-weight:700}
.site-footer .fnav{margin-bottom:6px}
.site-footer .fnav a{margin:0 7px}

/* ---------------------------------------------------- 词条悬停预览（Page Previews） */
/* position:fixed + 视口坐标：夹紧到视口时不用管页面滚到哪儿了（滚动本来就会收起卡片） */
.pv-card{position:fixed; z-index:200; width:340px; max-width:calc(100vw - 16px); background:#fff;
  border:1px solid var(--border); border-radius:3px; box-shadow:0 4px 14px rgba(0,0,0,.28);
  font-size:12.5px; line-height:1.65; color:var(--text); overflow:hidden; text-align:left}
.pv-card .pv-head{padding:5px 9px; font-size:13px; font-weight:700; color:#22456e;
  background:linear-gradient(180deg,var(--box-head-a),var(--box-head-b));
  border-bottom:1px solid var(--border); font-family:Georgia,"Songti SC","STSong",serif}
.pv-card .pv-head a{color:#22456e}
.pv-card .pv-body{display:flex; gap:9px; align-items:flex-start; padding:9px}
.pv-card .pv-thumb{flex:0 0 60px; width:60px; height:60px; object-fit:cover; background:#fff;
  border:1px solid var(--border-soft); padding:1px}
.pv-card .pv-text{margin:0; flex:1 1 auto; min-width:0; color:#333;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden}
.pv-card .pv-folded{color:#8a6d1f; font-size:12px; -webkit-line-clamp:2}
.pv-card .pv-body:only-child .pv-text{padding:0}
.pv-card .pv-foot{padding:3px 9px; text-align:right; font-size:11.5px; color:var(--muted);
  background:#f7fafd; border-top:1px solid var(--border-soft)}

@media (max-width:900px){
  .layout{flex-direction:column}
  /* 手机上正文排到侧栏前面。侧栏自己就有一屏多高，排在前面的话
     要先滚过「导航／作品分类／工具／关于」才看得到文章。 */
  .content{order:1}
  .sidebar{order:2; width:100%; flex:1 1 auto}
  .infobox{float:none; width:auto; margin:0 0 14px}
  .pagelist{columns:1}
  .search-form input{width:130px}
  .site-name{font-size:20px}
  .site-tagline{display:none}
}
@media (max-width:620px){
  /* 窄屏：顶栏那排链接和下面的导航条内容重复，收掉省地方 */
  .top-links{display:none}
  .search-form input{width:104px}
  .site-name{font-size:18px}
  .site-header-inner{gap:10px}
  .nav-inner>a{padding:8px 10px; font-size:12.5px}
  .layout{padding:0 10px; gap:12px}
  .article-wrap{padding:14px 13px 16px}
  h1.page-title{font-size:21px}
  .article h2{font-size:17px}
  .article h3{font-size:15px}
  .infobox{max-width:100%}
  /* 窄屏上横幅文字会折行，浮动的 [关闭] 会压到正文上，改成单独一行 */
  .spoiler-banner{padding-right:13px}
  .spoiler-banner .dismiss{float:none; display:block; text-align:right; margin-top:2px}
}
@media print{
  .top-bar,.nav-bar,.sidebar,.page-tabs,.site-footer,.search-form,.pv-card{display:none}
  .layout{display:block}
  .article-wrap{border:0; box-shadow:none}
  .spoiler-fold{border:0}
  .spoiler-fold .spoiler-body{display:block !important}
}
"""

THEME_JS = r"""
(function(){
  // ---------- 目录折叠 ----------
  document.querySelectorAll('.toc-head .toggle').forEach(function(t){
    t.addEventListener('click', function(){
      var box = t.closest('.toc');
      var list = box.querySelector('ol');
      var hidden = list.style.display === 'none';
      list.style.display = hidden ? '' : 'none';
      t.textContent = hidden ? '[隐藏]' : '[显示]';
    });
  });

  // ---------- 剧透折叠：记忆展开状态 ----------
  var KEY = 'wiki-spoiler-open';
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){}
  document.querySelectorAll('details.spoiler-fold').forEach(function(d){
    var id = (d.dataset.fold || '') + '@' + location.pathname;
    if (saved[id]) d.open = true;
    d.addEventListener('toggle', function(){
      saved[id] = d.open;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch(e){}
    });
  });

  // ---------- 顶部即时搜索 ----------
  var input = document.getElementById('wiki-search-input');
  var panel = document.getElementById('wiki-search-results');
  var indexUrl = input && input.getAttribute('data-index');
  // search.json 里的 u 是「相对站点根」的路径，而本下拉框会出现在任意深度的页面上，
  // 所以要补上「从当前页回到站点根」的前缀（例如 '../../'），否则在深层页点结果会 404。
  var basePrefix = indexUrl ? indexUrl.replace(/search\.json.*$/, '') : '';
  var data = null, loading = null, loadFailed = false;
  var FILE_HINT = '搜索需要本地服务器：双击打开 HTML 文件时浏览器不允许读取索引。' +
                  '请用 python3 build.py --open 预览，或直接访问发布在 GitHub Pages 上的站点。';

  function load(){
    if (data) return Promise.resolve(data);
    if (!loading) loading = fetch(indexUrl).then(function(r){ return r.json(); }).then(function(j){ data = j; return j; })
      .catch(function(){ loadFailed = true; data = []; return data; });
    return loading;
  }
  function render(list, q){
    if (loadFailed){ panel.innerHTML = '<div class="sr-none">' + FILE_HINT + '</div>'; return; }
    if (!list.length){ panel.innerHTML = '<div class="sr-none">没有找到「' + q + '」</div>'; return; }
    panel.innerHTML = list.slice(0, 12).map(function(p){
      var s = p.x ? p.x.slice(0, 60) + (p.x.length > 60 ? '…' : '') : '';
      return '<a href="' + basePrefix + p.u + '"><b>' + p.t + '</b><span class="sr-cat">' + (p.c || '') + '</span>' +
             (s ? '<br><span class="sr-cat">' + s + '</span>' : '') + '</a>';
    }).join('');
  }
  if (input && panel){
    input.addEventListener('input', function(){
      var q = input.value.trim();
      if (q.length < 1){ panel.classList.remove('on'); return; }
      load().then(function(all){
        var lower = q.toLowerCase();
        var hits = all.filter(function(p){
          return (p.t + ' ' + p.k + ' ' + (p.x || '')).toLowerCase().indexOf(lower) >= 0;
        }).sort(function(a, b){
          var at = a.t.toLowerCase().indexOf(lower) === 0 ? 0 : 1;
          var bt = b.t.toLowerCase().indexOf(lower) === 0 ? 0 : 1;
          return at - bt || b.n - a.n;
        });
        render(hits, q);
        panel.classList.add('on');
      });
    });
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter'){ e.preventDefault(); location.href = './search.html?q=' + encodeURIComponent(input.value.trim()); }
      if (e.key === 'Escape'){ panel.classList.remove('on'); input.blur(); }
    });
    document.addEventListener('click', function(e){
      if (!panel.contains(e.target) && e.target !== input) panel.classList.remove('on');
    });
  }

  // ---------- 剧透横幅关闭 ----------
  document.querySelectorAll('.spoiler-banner .dismiss').forEach(function(b){
    b.addEventListener('click', function(){ b.closest('.spoiler-banner').style.display = 'none'; });
  });

  // ---------- 词条导航折叠 ----------
  document.querySelectorAll('.navbox .nb-toggle').forEach(function(t){
    t.addEventListener('click', function(){
      var off = t.closest('.navbox').classList.toggle('collapsed');
      t.textContent = off ? '[展开]' : '[折叠]';
    });
  });

  // ---------- 词条悬停预览（Page Previews）----------
  // 鼠标停在蓝色词条链接上，浮出目标条目的标题、摘要和缩略图。
  // 数据来自构建期生成的 previews.json（加密作品不在里面，见 build.py）。
  (function(){
    // 触屏 / 只有粗指针的设备上没有「悬停」这回事，整套不启用。
    if (!window.matchMedia || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    if (typeof fetch !== 'function') return;

    var DELAY = 400;         // 悬停多久才弹（毫秒）
    var GRACE = 200;         // 离开链接/卡片后留一点时间，让人能把鼠标移进卡片
    var GAP = 6, EDGE = 8;
    var PV_VER = '__PREVIEWS_VER__';

    var input = document.getElementById('wiki-search-input');
    var indexUrl = input && input.getAttribute('data-index');
    if (!indexUrl) return;                       // 推不出去站点根的前缀，宁可不弹
    var basePrefix = indexUrl.replace(/search\.json.*$/, '');
    var indexFile = basePrefix + 'previews.json' +
                    (PV_VER ? '?v=' + encodeURIComponent(PV_VER) : '');

    // 站点根在 location 里的位置（GitHub Pages 是 /Wiki_for_flygonish/，本地是 /）。
    // 拿它才能把链接的 href（相对当前页面）还原成「相对站点根」，和 u 对得上。
    var rootPath = '';
    try {
      rootPath = new URL(basePrefix + 'previews.json', location.href).pathname.replace(/[^/]*$/, '');
    } catch (e) { rootPath = ''; }
    var selfPath = '';
    try {
      if (rootPath && location.pathname.indexOf(rootPath) === 0) {
        selfPath = safeDecode(location.pathname.slice(rootPath.length));
      }
    } catch (e) { selfPath = ''; }

    var items = null, loading = null, lookup = null;
    var card = null, cardLink = null;
    var hoveredLink = null, showTimer = null, hideTimer = null;

    function safeDecode(s){
      try { return decodeURIComponent(s); } catch (e) { return String(s); }
    }
    function normpath(p){
      var out = [];
      String(p).split('/').forEach(function(seg){
        if (!seg || seg === '.') return;
        if (seg === '..') { out.pop(); return; }
        out.push(seg);
      });
      return out.join('/');
    }
    function esc(s){
      return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }
    function encodePath(p){
      return String(p).split('/').map(function(seg){ return encodeURIComponent(seg); }).join('/');
    }
    // href（已去掉 # 与 ?query）→ 相对站点根的路径；外部链接 / 站外路径返回 ''
    function targetPath(href){
      var h = String(href || '').split('#')[0].split('?')[0];
      if (!h || h.indexOf('//') === 0 || /^[a-zA-Z][a-zA-Z0-9+.\-]*:/.test(h)) return '';
      var path = '';
      if (rootPath && typeof URL === 'function') {
        try { path = new URL(h, location.href).pathname; } catch (e) { return ''; }
        if (path.indexOf(rootPath) !== 0) return '';
        path = path.slice(rootPath.length);
      } else {
        // 老浏览器没有 URL：退回字符串拼接。href 里以 ../ 开头的会算错，
        // 这种链接宁可不弹卡片，也不弹错条目。
        if (h.charAt(0) === '/' || h.indexOf('../') === 0) return '';
        path = normpath(basePrefix + h);
      }
      return safeDecode(path);
    }

    function load(){
      if (items) return Promise.resolve(items);
      if (!loading) {
        loading = fetch(indexFile).then(function(r){ return r.json(); }).then(function(json){
          items = json || [];
          lookup = {};
          items.forEach(function(it){
            if (it && it.u) lookup[safeDecode(it.u)] = it;
          });
          return items;
        }).catch(function(){
          // 双击打开 HTML、或索引读取失败：安静地不弹卡片就是了
          items = []; lookup = {}; return items;
        });
      }
      return loading;
    }

    function hide(){
      clearTimeout(showTimer); clearTimeout(hideTimer);
      showTimer = hideTimer = null;
      if (card && card.parentNode) card.parentNode.removeChild(card);
      card = null; cardLink = null;
    }
    function scheduleHide(){
      clearTimeout(hideTimer);
      hideTimer = setTimeout(hide, GRACE);
    }
    function place(link){
      if (!card) return;
      var r = link.getBoundingClientRect();
      var vw = window.innerWidth || (document.documentElement && document.documentElement.clientWidth) || 0;
      var vh = window.innerHeight || (document.documentElement && document.documentElement.clientHeight) || 0;
      var cw = card.offsetWidth || 340;
      var ch = card.offsetHeight || 120;
      var left = r.left;
      var top = r.bottom + GAP;
      // 链接贴着视口底部时翻到上方
      if (top + ch + EDGE > vh && r.top - GAP - ch >= EDGE) top = r.top - GAP - ch;
      if (left + cw + EDGE > vw) left = vw - cw - EDGE;    // 右边放不下就左移
      if (left < EDGE) left = EDGE;
      if (top + ch + EDGE > vh) top = vh - ch - EDGE;      // 上下都夹进视口
      if (top < EDGE) top = EDGE;
      card.style.left = Math.round(left) + 'px';
      card.style.top = Math.round(top) + 'px';
    }
    function show(link, item){
      if (card && cardLink === link) return;      // 同一个链接不重复建 DOM
      hide();
      cardLink = link;
      card = document.createElement('div');
      card.className = 'pv-card';
      card.id = 'pv-card';
      var href = esc(basePrefix + item.u);
      var html = '<div class="pv-head"><a href="' + href + '">' + esc(item.t) + '</a></div>';
      var body = '';
      if (item.i) {
        body += '<img class="pv-thumb" src="' + esc(basePrefix + encodePath(item.i)) + '" alt="">';
      }
      if (item.x) {
        body += '<p class="pv-text">' + esc(item.x) + '</p>';
      } else if (item.f) {
        // 正文全在剧透折叠里：不拿折叠内容当摘要，但别让卡片空着
        body += '<p class="pv-text pv-folded">\uD83D\uDD12 本页正文默认折叠，点开查看</p>';
      }
      if (body) html += '<div class="pv-body">' + body + '</div>';
      html += '<div class="pv-foot"><a href="' + href + '">查看条目 \u2192</a></div>';
      card.innerHTML = html;
      card.addEventListener('mouseenter', function(){ clearTimeout(hideTimer); hideTimer = null; });
      card.addEventListener('mouseleave', scheduleHide);
      document.body.appendChild(card);
      place(link);
    }
    function open(link){
      showTimer = null;
      var key = targetPath(link.getAttribute('href'));
      // 查不到条目（含加密作品、未完成页面）就不弹——不做任何兜底猜测
      if (!key || key === selfPath) return;
      load().then(function(){
        if (hoveredLink !== link) return;       // 等数据的时候鼠标已经移开了
        if (!lookup || !lookup[key]) return;
        show(link, lookup[key]);
      });
    }

    document.addEventListener('mouseover', function(e){
      var t = e.target;
      var link = t && t.closest ? t.closest('a.wikilink') : null;
      if (link) {
        clearTimeout(hideTimer); hideTimer = null;
        if (card && cardLink !== link) hide();          // 同一时间只留一张卡片
        if (card) return;
        hoveredLink = link;
        clearTimeout(showTimer);
        showTimer = setTimeout(function(){ open(link); }, DELAY);
        return;
      }
      if (card && (t === card || card.contains(t))) { clearTimeout(hideTimer); hideTimer = null; }
    });
    document.addEventListener('mouseout', function(e){
      var t = e.target;
      var link = t && t.closest ? t.closest('a.wikilink') : null;
      if (!link) return;
      if (hoveredLink === link) hoveredLink = null;
      var to = e.relatedTarget;
      if (to && (link.contains(to) || (card && card.contains(to)))) return;   // 移进卡片，别收
      clearTimeout(showTimer); showTimer = null;
      scheduleHide();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape' || e.keyCode === 27) hide();
    });
    document.addEventListener('click', function(e){
      if (card && !card.contains(e.target)) hide();     // 点了别处
    });
    window.addEventListener('scroll', hide, true);      // 页面一动，卡片就不跟了
    window.addEventListener('resize', hide);
  })();
})();
"""

# theme.js 里给 previews.json 留的缓存指纹占位符，build.py 写盘时替换成 _asset_ver
PREVIEW_VER_TOKEN = "__PREVIEWS_VER__"

SEARCH_JS = r"""
(function(){
  var form = document.getElementById('sform');
  var box = document.getElementById('sresults');
  var input = document.getElementById('q');
  var params = new URLSearchParams(location.search);
  var initial = params.get('q') || '';
  input.value = initial;
  box.setAttribute('data-index', 'search.json');

  fetch('search.json').then(function(r){ return r.json(); }).then(function(all){
    run(initial, all);
    form.addEventListener('submit', function(e){
      e.preventDefault();
      var u = new URL(location.href); u.searchParams.set('q', input.value); history.replaceState(null, '', u);
      run(input.value, all);
    });
    input.addEventListener('input', function(){ run(input.value, all); });
  }).catch(function(){ box.innerHTML = '<p class="hit-count">搜索索引加载失败。' +
      '如果你是双击打开 HTML 文件，浏览器会禁止读取索引——请改用 ' +
      '<code>python3 build.py --open</code> 预览，或访问已发布的站点。</p>'; });

  function run(q, all){
    q = (q || '').trim();
    if (!q){ box.innerHTML = '<p class="hit-count">这个 wiki 共收录 ' + all.length + ' 个页面。输入关键词开始搜索。</p>'; return; }
    var lower = q.toLowerCase();
    var hits = all.filter(function(p){
      return (p.t + ' ' + p.k + ' ' + (p.x || '')).toLowerCase().indexOf(lower) >= 0;
    });
    if (!hits.length){ box.innerHTML = '<p class="hit-count">没有找到「' + q + '」。</p>'; return; }
    box.innerHTML = '<p class="hit-count">找到 ' + hits.length + ' 个页面：</p>' + hits.map(function(p){
      return '<div class="recent-row"><div style="flex:1 1 auto"><a href="' + p.u + '"><b>' + p.t + '</b></a>' +
             ' <span class="sr-cat">' + (p.w || '') + (p.c ? ' › ' + p.c : '') + '</span>' +
             (p.x ? '<div class="sr-cat">' + p.x.slice(0, 130) + '…</div>' : '') + '</div></div>';
    }).join('');
  }
})();
"""

RANDOM_JS = r"""
fetch('search.json').then(function(r){ return r.json(); }).then(function(all){
  document.getElementById('cnt').textContent = all.length;
  document.getElementById('go').addEventListener('click', function(){
    location.href = all[Math.floor(Math.random() * all.length)].u;
  });
  var p = new URLSearchParams(location.search).get('go');
  if (p) location.href = all[Math.floor(Math.random() * all.length)].u;
});
"""


def esc(s):
    return _html.escape(str(s if s is not None else ""), quote=True)


def theme_css(theme):
    t = dict(theme)
    t.setdefault("accent", "#3a6ea5")
    t.setdefault("accent2", "#2a4f78")
    t.setdefault("accent3", "#5a92c8")
    t.setdefault("link", "#0b5fa5")
    t.setdefault("link_visited", "#0b4a80")
    t.setdefault("red", "#ba0000")
    t.setdefault("page_bg", "#eef1f4")
    t.setdefault("border", "#b9c9d9")
    t.setdefault("border_soft", "#dbe5ee")
    t.setdefault("box_head_a", "#eef5fb")
    t.setdefault("box_head_b", "#dde9f4")
    t.setdefault("mark", "#fff3a3")
    css = THEME_CSS
    for k, v in t.items():
        css = css.replace("{{%s}}" % k, str(v))
    return css


class Site:
    """页面外壳需要的站点级数据。"""

    def __init__(self, config, nav, sidebar_boxes, index_json_url="search.json"):
        self.config = config
        self.nav = nav
        self.sidebar_boxes = sidebar_boxes

    @property
    def name(self):
        return self.config.get("site_name", "Wiki")

    @property
    def tagline(self):
        return self.config.get("site_tagline", "")

    @property
    def repo(self):
        return self.config.get("repo", {})


def render_layout(site, *, title, body, rel, current_page=None, article_class="article",
                  page_tabs=None, subtitle="", catlinks="", backlinks="", head_extra="",
                  description="", nav_active="", sidebar_active="", top_extra="",
                  banner="", stats_line="", titleblock="", navbox=""):
    """生成整页 HTML。rel 是回到 docs/ 根的相对前缀，形如 '../..' 或 '..'，首页为 ''。"""
    base = rel
    repo = site.repo
    edit_url = history_url = ""
    if repo.get("url") and current_page is not None and repo.get("edit"):
        branch = repo.get("branch", "main")
        src = repo.get("content_path", "content")
        path = current_page.rel.replace(" ", "%20")
        edit_url = "%s/edit/%s/%s/%s" % (repo["url"], branch, src, path)
        history_url = "%s/commits/%s/%s/%s" % (repo["url"], branch, src, path)

    tabs = ['<div class="page-tabs">']
    if page_tabs is None:
        tabs.append('<span class="tab active">页面</span>')
        tabs.append('<span class="tab disabled" title="静态站不提供讨论区">讨论</span>')
        tabs.append('<span class="tab spacer"></span>')
        if edit_url:
            tabs.append('<a class="tab" href="%s" target="_blank" rel="noopener">编辑</a>' % esc(edit_url))
            tabs.append('<a class="tab" href="%s" target="_blank" rel="noopener">历史</a>' % esc(history_url))
    else:
        tabs.append(page_tabs)
    tabs.append("</div>")

    logo = site.config.get("logo", "")
    if logo:
        logo_html = '<img src="%sassets/%s" alt="logo">' % (base, esc(logo))
    else:
        logo_html = FAVICON

    nav_html = "".join(
        '<a class="%s" href="%s%s">%s</a>' % ("on" if key == nav_active else "", base, esc(url), esc(label))
        for label, url, key in site.nav)

    sb = []
    for box in site.sidebar_boxes:
        cls = "box on" if box.get("key") and box["key"] == sidebar_active else "box"
        sb.append('<div class="%s">' % cls)
        if box.get("title"):
            ic = icon(box.get("icon"), base)
            if box.get("href"):
                sb.append('<a class="work-title" href="%s%s">%s%s</a>'
                          % (base, esc(box["href"]), ic, esc(box["title"])))
            else:
                sb.append('<div class="box-title">%s%s</div>' % (ic, esc(box["title"])))
        if box.get("html"):
            sb.append(box["html"])
        elif box.get("items"):
            sb.append("<ul>")
            for it in box["items"]:
                if it is None:
                    sb.append('<li class="sub">—</li>')
                    continue
                label, url, extra, on = it
                cnt = '<span class="cnt">%s</span>' % extra if extra else ""
                sb.append('<li class="%s"><a href="%s%s">%s%s</a></li>'
                          % ("on" if on else "", base, esc(url), esc(label), cnt))
            sb.append("</ul>")
        sb.append("</div>")

    # ---- 站点图标 / 社交缩略图 ----
    icon_file = site.config.get("icon") or "favicon.svg"   # 注意别叫 icon，会遮住上面的 icon() 函数
    apple = site.config.get("apple_icon") or ""
    apple_meta = ('<link rel="apple-touch-icon" href="%sassets/%s">' % (base, esc(apple))
                  if apple else "")
    site_url = (site.config.get("site_url") or "").rstrip("/")
    og_image = site.config.get("og_image") or ""
    og = ['<meta property="og:type" content="website">',
          '<meta property="og:site_name" content="%s">' % esc(site.name),
          '<meta property="og:title" content="%s">' % esc(title),
          '<meta property="og:description" content="%s">' % esc(description or site.tagline),
          '<meta name="twitter:card" content="summary_large_image">']
    if site_url and og_image:
        og.append('<meta property="og:image" content="%s/assets/%s">' % (site_url, esc(og_image)))
        og.append('<meta property="og:image:width" content="1200">')
        og.append('<meta property="og:image:height" content="630">')
    if site_url and current_page is not None:
        og.append('<link rel="canonical" href="%s/%s">' % (site_url, current_page.out_path))

    # ---- 页脚 88x31 小按钮 ----
    btns = []
    for b in site.config.get("buttons", []) or []:
        img = '<img src="%sassets/%s" alt="%s" width="88" height="31">' % (
            base, esc(b["img"]), esc(b.get("alt", "")))
        href = b.get("href")
        if href:
            target = ' target="_blank" rel="noopener"' if b.get("ext") else ""
            if not b.get("ext"):
                href = base + href
            btns.append('<a class="sbtn" href="%s"%s title="%s">%s</a>'
                        % (esc(href), target, esc(b.get("title", b.get("alt", ""))), img))
        else:
            btns.append('<span class="sbtn" title="%s">%s</span>'
                        % (esc(b.get("title", b.get("alt", ""))), img))
    buttons_html = ('<div class="sbtn-row">%s</div>' % "".join(btns)) if btns else ""

    return """<!DOCTYPE html>
<html lang="%(lang)s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<meta name="generator" content="nijiboshi-wiki builder">
<link rel="icon" href="%(base)sassets/%(icon)s">
%(apple_icon_meta)s
<link rel="stylesheet" href="%(base)sassets/theme.css?v=%(asset_ver)s">
%(og_meta)s
%(head_extra)s
</head>
<body>
<div class="top-bar"><div class="top-inner">
  <span class="global-brand"><b>%(sitename)s</b> · 维基</span>
  <span class="top-links">
    <a href="%(base)sall.html">所有页面</a>
    <a href="%(base)srecent.html">最近更新</a>
    <a href="%(base)srandom.html">随机页面</a>
    %(repolink)s
  </span>
</div></div>

<div class="site-header"><div class="site-header-inner">
  <a class="logo-box" href="%(base)sindex.html">%(logo)s</a>
  <div class="site-id">
    <a class="site-name" href="%(base)sindex.html">%(sitename)s</a>
    <span class="site-tagline">%(tagline)s</span>
  </div>
  <div class="header-right">
    <form class="search-form" action="%(base)ssearch.html" method="get" onsubmit="return true">
      <input id="wiki-search-input" name="q" type="search" autocomplete="off" placeholder="搜索本维基…" data-index="%(base)ssearch.json">
      <button type="submit">搜索</button>
      <div class="search-results" id="wiki-search-results"></div>
    </form>
  </div>
</div></div>

<div class="nav-bar"><div class="nav-inner">%(nav)s</div></div>

<div class="layout">
  <aside class="sidebar">%(sidebar)s</aside>
  <main class="content">
    %(tabs)s
    <div class="article-wrap">
      %(banner)s
      %(titleblock)s
      <div class="%(article_class)s">%(body)s</div>
      %(backlinks)s
      %(navbox)s
      %(catlinks)s
    </div>
  </main>
</div>

<footer class="site-footer">
  %(buttons)s
  <div class="fnav">
    <a href="%(base)sindex.html">首页</a>·
    <a href="%(base)sall.html">所有页面</a>·
    <a href="%(base)srecent.html">最近更新</a>·
    <a href="%(base)ssearch.html">搜索</a>·
    <a href="%(base)sspecial.html">特殊页面</a>·
    <a href="%(base)smissing.html">未完成的页面</a>·
    <a href="%(base)s小按钮.html">小按钮</a>
  </div>
  <div>%(footnote)s</div>
  %(icon_credit)s
  <div style="margin-top:5px">%(stats)s</div>
</footer>
<script src="%(base)sassets/theme.js?v=%(asset_ver)s"></script>
%(body_extra)s
</body>
</html>
""" % {
        "lang": site.config.get("language", "zh-CN"),
        "title": esc(title),
        "desc": esc(description or site.tagline),
        "base": base,
        "sitename": esc(site.name),
        "tagline": esc(site.tagline),
        "logo": logo_html,
        "nav": nav_html,
        "sidebar": "\n".join(sb),
        "tabs": "\n".join(tabs),
        "banner": banner,
        "titleblock": titleblock,
        "article_class": article_class,
        "body": body,
        "catlinks": catlinks,
        "backlinks": backlinks,
        "navbox": navbox,
        "head_extra": head_extra,
        "body_extra": top_extra,
        "icon": esc(icon_file),
        "apple_icon_meta": apple_meta,
        "og_meta": "\n".join(og),
        "buttons": buttons_html,
        "asset_ver": esc(site.config.get("_asset_ver", "")),
        "icon_credit": ('<div class="credit">%s</div>' % site.config["icon_credit"])
                       if site.config.get("icon_credit") else "",
        "footnote": site.config.get("footer", ""),
        "stats": stats_line,
        "repolink": ('<a href="%s" target="_blank" rel="noopener">GitHub 仓库</a>' % esc(repo["url"]))
                    if repo.get("url") else "",
    }


def page_title_block(h1, subtitle_items=None):
    out = ['<h1 class="page-title">%s</h1>' % h1]
    if subtitle_items:
        out.append('<div class="page-subtitle">%s</div>'
                   % '<span class="sep">|</span>'.join(subtitle_items))
    return "\n".join(out)


def toc_html(headings, has_spoiler):
    # 只列 h2/h3，且排除嵌套在 callout / 信息框 / 引用块里的标题
    listed = [h for h in headings if 2 <= h["level"] <= 3 and not h.get("nested")]
    if len(listed) < 3:
        return ""
    out = ['<div class="toc"><div class="toc-head">目录 <span class="toggle">[隐藏]</span></div><ol>']
    level = 2
    for h in listed:
        if h["level"] > level:
            out.append("<ol>")
        elif h["level"] < level:
            out.append("</ol>")
        lock = ' <span class="lock" title="该段含剧透，默认折叠">🔒</span>' if h["spoiler"] else ""
        out.append('<li><a href="#%s">%s</a>%s</li>' % (h["anchor"], esc(h["text"]), lock))
        level = h["level"]
    while level > 2:
        out.append("</ol>")
        level -= 1
    out.append("</ol></div>")
    return "".join(out)


def spoiler_banner(text):
    return ('<div class="spoiler-banner"><span class="dismiss" title="关闭提示">[关闭]</span>'
            '<b>⚠ 剧透警告</b> — %s</div>' % text)


def catlinks_html(links):
    if not links:
        return ""
    return '<div class="catlinks">分类：%s</div>' % " · ".join(
        '<a href="%s">%s</a>' % (esc(u), esc(t)) for t, u in links)


def backlinks_html(items):
    if not items:
        return ""
    body = "、".join('<a href="%s">%s</a>' % (esc(u), esc(t)) for t, u in items)
    return '<div class="backlinks" id="backlinks"><div class="bl-title">链入本页的页面（%d）</div>%s</div>' % (
        len(items), body)


MBOX_KINDS = {
    "内容": ("mbox-content", "information.png"),
    "扩充": ("mbox-content", "pencil.png"),
    "小作品": ("mbox-content", "pencil.png"),
    "清理": ("mbox-clean", "exclamation.png"),
    "翻译": ("mbox-clean", "exclamation.png"),
    "来源": ("mbox-clean", "exclamation.png"),
    "警告": ("mbox-warn", "exclamation.png"),
}

# 状态 → 提示文字。frontmatter 里写「状态: 扩充」即可
STATUS_TEXT = {
    "扩充": "本条目内容还比较少，欢迎补充。",
    "小作品": "这是一篇小作品。你可以帮忙扩充它。",
    "清理": "本条目需要清理，格式或行文可能需要调整。",
    "翻译": "本条目有未翻译的内容。",
    "来源": "本条目缺少来源，欢迎补充出处。",
    "警告": "本条目包含可能引起不适的内容。",
}


def mbox(status, text=None, base=""):
    """MediaWiki 那种消息框（模板 {{mbox}} 的位置）。"""
    kind, ico = MBOX_KINDS.get(status, ("mbox-content", "information.png"))
    body = text or STATUS_TEXT.get(status, "")
    if not body:
        return ""
    return ('<div class="mbox %s"><span class="mbox-icon">%s</span>'
            '<span class="mbox-text">%s</span></div>'
            % (kind, icon(ico, base, 16), body))


def navbox_html(title, groups, view_url="", edit_url="", collapsed=False):
    """MediaWiki 那种「词条导航盒」。

    groups 结构：
        [{"label": "角色", "rows": [{"label": "自机", "items": [(显示名, url, 是否红链)]}]},
         {"label": "场景",  "items": [(...)]}]
    单层的直接给 items，双层的给 rows。
    """
    if not groups:
        return ""

    def one_line(items):
        parts = []
        for text, url, missing in items:
            cls = ' class="nb-missing"' if missing else ""
            parts.append('<a%s href="%s">%s</a>' % (cls, esc(url), esc(text)))
        return '<span class="nb-sep">·</span>'.join(parts)

    rows_html = []
    for g in groups:
        sub = g.get("rows")
        if sub:
            for i, r in enumerate(sub):
                head = ('<th class="nb-group" rowspan="%d">%s</th>' % (len(sub), esc(g["label"]))
                        if i == 0 else "")
                rows_html.append('<tr>%s<th class="nb-sub">%s</th><td class="nb-list">%s</td></tr>'
                                 % (head, esc(r.get("label", "")), one_line(r.get("items", []))))
        else:
            rows_html.append('<tr><th class="nb-group">%s</th><td class="nb-list" colspan="2">%s</td></tr>'
                             % (esc(g["label"]), one_line(g.get("items", []))))

    links = []
    if view_url:
        links.append('<a href="%s" title="查看该作品的条目总览">查</a>' % esc(view_url))
    if edit_url:
        links.append('<a href="%s" target="_blank" rel="noopener" title="在 GitHub 上编辑这个导航">编</a>'
                     % esc(edit_url))
    head_links = '<span class="nb-sep">·</span>'.join(links)

    return ('<div class="navbox%s">'
            '<div class="navbox-head">'
            '<span class="nb-links">%s</span>'
            '<span class="nb-title">%s</span>'
            '<span class="nb-toggle" title="收起或展开这个导航">%s</span>'
            '</div>'
            '<table class="navbox-table">%s</table>'
            '</div>') % (" collapsed" if collapsed else "", head_links, esc(title),
                         "[展开]" if collapsed else "[折叠]", "".join(rows_html))


def now_str():
    return datetime.date.today().strftime("%Y-%m-%d")
