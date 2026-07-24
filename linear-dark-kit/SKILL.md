---
name: linear-dark-kit
description: 用锁定的 Linear 冷峻暗色设计系统，零依赖地构建高质感单文件 HTML 工具 / 聚合门户。提供设计 tokens、可复制的章节模板（导航/非对称 Hero/卡片网格/数据背书/FAQ/CTA/主题切换）、13 个线性 SVG 图标、离线优先规范与测试脚手架。当用户要把单文件工具做得「像作品集」而非「能用就行」时使用。
---

# Linear Dark Kit —— 单文件工具的高质感设计系统

为「单文件 / 零依赖 / 本地优先」的网页工具提供一套**锁定、可复用**的 Linear 冷峻暗色视觉语言，让每个新工具天生同款质感，不必每次重调。配合 `single-file-html-tool` 技能的「构建→测试→开源」流水线使用。

## 何时用
- 用户要做一个**高质感**的单文件网页工具 / 聚合门户，而不是「能用就行」的草稿。
- 你已经在用 `single-file-html-tool` 做工具，需要统一的视觉系统（配色、字体、间距、章节模板、图标）。
- 需要一套可复制粘贴的页面章节（Hero / 网格 / FAQ / CTA）和统一的图标集。
- 要避开 AI 生成页面常见的「渐变球 / Inter 字体 / 纯黑底 / 三等列卡片」cliché。

## 核心原则（务必遵守）
1. **零外部请求**：不引 CDN、不引网络字体、不引图片。系统字体栈 + 内联 SVG 图标。
2. **唯一强调色**：只用 `#5E6AD2`（Linear 靛蓝，饱和度 ~55% < 80%）。禁止多色霓虹、禁止 AI 紫蓝渐变光。
3. **离线优先 + 性能**：只动 `transform`/`opacity`；`IntersectionObserver` 揭示；`prefers-reduced-motion` 降级。
4. **可测试架构**：核心逻辑写纯函数并 `module.exports` 导出（见 `single-file-html-tool`）；UI 用 `data-theme` + `localStorage` 切主题。
5. **禁止清单（踩中即「AI 味」）**：
   - 不出现 Inter / 任何需要下载的网络字体
   - 不要纯黑 `#000000` 画布（用 `#0A0A0B`）
   - 不要 AI 渐变球 / 紫蓝光晕
   - 不要「三等列等宽卡片」堆砌
   - 文本节点里**不要 emoji**（图标用线性 SVG 框）

## 设计 tokens（权威值见 `references/design-tokens.md`）
- 画布 `#0A0A0B`／卡片 `#141417`／次级面 `#1A1B1E`
- 文本 `#FFFFFF` `#A1A1AA`(zinc-400) `#71717A`(zinc-500)
- 边框 `rgba(255,255,255,0.08)`（强边框 `0.14`）
- 强调 `#5E6AD2`／成功 `#10B981`／警告 `#F5A623`／错误 `#FF4D4F`
- 圆角 6–14px；内容最大宽 ~1180px

## 怎么组装一个页面
1. 从 `assets/template.html` 起步（已含 CSS 变量、主题切换、揭示动效、`.wrap` 容器）。
2. 按需复制 `references/page-templates.md` 里的章节片段：导航 → 非对称 Hero（左文 + 右 CSS 浏览器预览 mockup）→ 三大卖点 → 工具网格（SVG 图标 + 角标 + 搜索/筛选）→ 数据背书 → FAQ(`<details>`) → 结尾 CTA → 页脚。
3. 图标用 `references/icons.md` 的 13 个线性 SVG（单色 `currentColor`），通过 `iconSvg(key)` 注入；新增工具加一项 `ICONS[key]` 即可。
4. 纯函数 + `module.exports` + 主题守卫（用真实存在的元素判断，别用不存在的 id，否则全页事件失效）。
5. 测试/开源走 `single-file-html-tool` 流水线：纯函数单测 + jsdom 真机功能测试（`_test.js` 用 `__dirname` 读文件，可移植），再开仓库 + Pages + Topics + 徽章。

## 文件地图
- `references/design-tokens.md` —— 全部颜色/间距/圆角/字体/阴影/动效的精确值。
- `references/page-templates.md` —— 各章节的可复制 HTML/CSS/JS 片段。
- `references/icons.md` —— 13 个线性 SVG 图标 + `iconSvg()` 封装。
- `assets/template.html` —— 开箱即用的单文件起点（含示例纯函数 + 测试钩子注释）。
