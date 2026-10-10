# 读毛选 · 毛泽东选集在线阅读

**在线阅读：<https://risingrode.github.io/dumaoxuan/>**

《毛泽东选集》七卷 392 篇在线阅读，配有面向普通读者的白话注解和历史背景，手机、电脑都能用，打开网页就能读，不用安装。

## 功能

- **全七卷 392 篇**：第一至五卷为官方出版版本，第六、七卷为非官方整理版本（见下方说明）
- **一句话读懂 + 核心要点**：每篇开头先用大白话说清楚讲了什么、为什么重要
- **文章导读**：写作背景、党史意义、相关历史事件
- **白话注解**：点击正文中标亮的句子，右侧（手机上为底部）弹出通俗注解和历史背景
- **名词解释**：正文里人名、地名、组织、时代术语带虚线标注，点一下就显示解释
- **情景分析练习**：部分篇目配有练习卡片，读完可以自测理解
- **全文搜索**：按篇名或正文内容检索
- **书签**：收藏注解，随时回看
- **阅读进度**：自动记录已读篇目，按卷统计进度
- **阅读体验**：字号调节、衬线/无衬线字体切换、暗色模式；注解可生成分享链接
- **可安装**：支持添加到手机主屏幕（PWA）

阅读记录、书签和设置都只保存在你自己的浏览器里，没有账号，也不上传任何数据。

## 本地运行

只需要 Python 3，没有第三方依赖：

```bash
python server.py
# 打开 http://localhost:8080
```

## 部署

网站部署在 GitHub Pages，推送到 `main` 分支后由 GitHub Actions（`.github/workflows/pages.yml`）自动构建发布，约 1 分钟生效。

GitHub Pages 只能托管静态文件，所以构建时由 `build_static.py` 把 `server.py` 的全部 `/api` 接口预先生成为 JSON 文件（输出到 `_site/`），并在页面中注入一小段转接代码，搜索改在浏览器端完成。本地预览静态版：

```bash
python build_static.py
cd _site && python -m http.server
```

## 目录结构

```
index.html            前端（单文件）
server.py             本地服务器，提供 /api 接口
build_static.py       生成静态站点（GitHub Pages 用）
annotations/
  data.py             各篇导读与注解
  cards.py            情景分析练习卡片
MaoZeDongAnthology/   原文（Markdown）
.github/workflows/    自动部署
```

### 注解数据格式

`annotations/data.py` 中每篇文章一条：

```python
ANNOTATIONS = {
    1: {
        'meta': {
            'hook': '引子',
            'context': '写作背景',
            'party_history': '党史意义',
            'events': ['相关历史事件', ...],
            'summary': '一句话读懂',
            'keypoints': ['核心要点', ...],
            'terms': [{'t': '原文中的词', 'd': '解释'}, ...],  # 网页在正文中标出，点击显示
        },
        'paragraphs': [
            {
                'match': '原文中的一段逐字文字',  # 锚点，全文唯一；网页标亮从这里到句末
                'note': '通俗注解',
                'bg': '历史背景（可选）',
                'story': '历史细节或类比（可选）',
            },
        ],
    },
}
```

## 原文来源与说明

原文来自 [MaoZeDongAnthology](MaoZeDongAnthology/README.md) 整理的 Markdown 版本，部分内容整理自 [Selected-Works-of-Mao-Zedong-JingHuo-version](https://github.com/lindaye6/Selected-Works-of-Mao-Zedong-JingHuo-version)。

- 第一至第五卷为官方出版版本；**第六、七卷为「静火」非官方整理版本，可能存在错误或来源存疑的内容，请注意鉴别。**
- 注解与导读为学习辅助材料，力求准确、客观；史实以主流史学研究和原书题解、注释为准。发现错误欢迎提 Issue 或 Pull Request。
