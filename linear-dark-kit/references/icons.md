# 线性 SVG 图标集（单色 currentColor，离线安全）

统一描边风格：`viewBox="0 0 24 24"`、`stroke="currentColor"`、`stroke-width="1.8"`、`stroke-linecap/linejoin="round"`、`fill="none"`。颜色跟随父级 `color`（默认 `--text-2`，hover 变 `--accent`）。

## 封装函数
```js
var ICONS = {
  regex:'<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
  cron:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  diff:'<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="M16 21l4-4-4-4"/><path d="M20 17H4"/>',
  context:'<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>',
  box:'<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  notes:'<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  node:'<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>',
  chart:'<path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
  convert:'<path d="M17 2l4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
  color:'<path d="M12 2.7l5.7 5.7a8 8 0 1 1-11.4 0z"/>',
  hash:'<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
  json:'<path d="M8 3H7a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h1"/><path d="M16 3h1a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-1"/>'
};
function iconSvg(k){
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
       + 'stroke-linecap="round" stroke-linejoin="round">'+(ICONS[k]||"")+'</svg>';
}
```

## 在网格里用
```js
'<div class="card-ico">'+iconSvg(t.icon)+'</div>'
```

## 语义对应（按需扩写）
| key | 含义 | 适用工具 |
|-----|------|----------|
| regex | 闪电/正则 | RegexLab |
| cron | 时钟 | CronText |
| diff | 双向箭头 | DiffLens |
| context | 窗口/上下文 | ContextLens |
| box | 立方体 | BoxKit |
| notes | 文档 | Inkwell |
| node | 节点图 | Graphite |
| chart | 柱状图 | Chartify |
| convert | 双向转换 | UniConvert |
| image | 图片 | SnapCompress |
| color | 水滴/色 | PalettePro |
| hash | # 号 | HashKit |
| json | 花括号 | JsonForge |

新增工具时，往 `ICONS` 加一项并保持同款描边即可，渲染自动生效。
