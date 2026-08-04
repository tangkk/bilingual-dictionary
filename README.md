# 双向词典 · Chinese ↔ English

一个完全静态、可部署到 GitHub Pages 的中英双向词典。查询在浏览器本地完成，不需要服务器、数据库或 API Key。

词典数据来自：

- [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict)：中文、繁体、拼音及英文释义；
- [FreeDict English–Chinese](https://freedict.org/downloads/)：英文词条、读音、词性及中文释义；
- [jieba](https://github.com/fxsjy/jieba)：中文词性标签；
- [Tatoeba](https://tatoeba.org/downloads)：带作者信息的中英双语例句。

## 功能

- 自动识别中文或英文输入；
- 简体中文、繁体中文 → 英文；
- 英文单词及短语 → 中文；
- CC-CEDICT 英文释义反向索引；
- 英文发音、词性及中文拼音展示；
- 中文词性标签，并将缩写转换为中文名称；
- 每个查询词最多三组 Tatoeba 中英例句；
- 第一组例句直接展示，其余例句可展开查看；
- 前缀相关词语建议；
- 最近查询记录仅保存在当前浏览器；
- 查询可通过 `?q=apple` 链接分享；
- 无第三方运行时依赖，适合 GitHub Pages。

## 项目结构

```text
.
├── public/                  # GitHub Pages 发布目录
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── licenses.html
├── scripts/
│   └── build_dictionary.py # 将两套原始数据生成分片 JSON
├── vendor/
│   ├── cc-cedict/
│   ├── freedict/
│   ├── jieba/
│   └── tatoeba/
└── .github/workflows/pages.yml
```

`public/data/` 是构建产物，默认不提交到 Git。GitHub Actions 每次发布时都会重新生成。

## 本地运行

需要 Python 3.10 或更新版本。

```bash
python3 scripts/build_dictionary.py
python3 -m http.server 8000 --directory public
```

然后打开 <http://localhost:8000>。

不要直接双击 `public/index.html`，浏览器通常不允许本地页面通过 `fetch()` 读取分片数据。

## 更新词典数据

下载最新数据并替换对应文件：

```bash
curl -L https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz \
  -o vendor/cc-cedict/cedict.txt.gz

curl -L https://download.freedict.org/generated/eng-zho/eng-zho.tei \
  -o vendor/freedict/eng-zho.tei

curl -L https://download.freedict.org/generated/eng-zho/COPYING \
  -o vendor/freedict/COPYING

curl -L https://raw.githubusercontent.com/fxsjy/jieba/master/jieba/dict.txt \
  -o vendor/jieba/dict.txt

curl -L https://downloads.tatoeba.org/exports/per_language/cmn/cmn-eng_links.tsv.bz2 \
  -o vendor/tatoeba/cmn-eng_links.tsv.bz2

curl -L https://downloads.tatoeba.org/exports/per_language/cmn/cmn_sentences_detailed.tsv.bz2 \
  -o vendor/tatoeba/cmn_sentences_detailed.tsv.bz2

curl -L https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2 \
  -o vendor/tatoeba/eng_sentences_detailed.tsv.bz2

python3 scripts/build_dictionary.py
```

构建完成后，`public/data/manifest.json` 会记录数据版本、词条数量和构建时间。

## 部署到 GitHub Pages

1. 在 GitHub 创建一个空仓库。
2. 将本项目提交并推送到仓库的 `main` 分支。
3. 打开仓库的 **Settings → Pages**。
4. 在 **Build and deployment → Source** 中选择 **GitHub Actions**。
5. 打开 **Actions** 页面等待 `Deploy dictionary to GitHub Pages` 完成。

之后每次推送到 `main` 都会自动重新构建词典并发布。

## 搜索数据设计

为了避免首次打开时下载整部词典，构建脚本将数据拆成小型 JSON：

- 中文根据首个汉字的 Unicode 编码分配到 256 个固定分片；
- 英文按规范化后的前两个字母或数字分片；
- 查询时只下载相关分片，并在内存中缓存。

FreeDict 结果在英译中查询中优先显示；CC-CEDICT 的反向索引用于补充词语和专名覆盖。

例句构建过程先读取 Tatoeba 的中英链接和作者信息，再按句长、词数和字符质量排序。英文使用连续词组匹配，中文使用词语子串匹配；每个检索词只发布质量较高的前三组例句。例句页链接和作者用户名用于保留来源署名。

## 许可证

网站程序代码采用 [MIT License](./LICENSE)。词典数据不适用 MIT License：

- CC-CEDICT 数据采用 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)；
- FreeDict English–Chinese 数据采用 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)；
- FreeDict 的基础数据来自 Wiktionary，经 DBnary 与 WikDict 处理。
- jieba 词典采用 [MIT License](https://github.com/fxsjy/jieba/blob/master/LICENSE)；
- Tatoeba 例句采用 [CC BY 2.0 FR](https://creativecommons.org/licenses/by/2.0/fr/deed.en)，页面保留原句链接和作者信息。

本项目对原始词典进行了格式转换、索引生成和分片处理。再发布生成的数据时，请保留署名、来源链接和相应的 ShareAlike 许可证说明。完整说明也展示在网站的“数据来源与许可证”页面。

## 设计

界面采用黑、白、灰色系统，使用系统字体、细边框、圆角输入框和紧凑卡片布局，视觉语言参考 `web-realbook`，并针对词典查询和移动设备重新组织。
