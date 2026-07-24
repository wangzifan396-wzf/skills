# Linear Dark Kit —— 设计 Tokens（权威值）

复制 `:root` 块到 `<style>` 顶部即可启用整套系统。浅色主题通过 `[data-theme="light"]` 覆盖变量，JS 切 `document.documentElement.dataset.theme` 并写 `localStorage`。

```css
:root{
  /* 表面 */
  --bg:#0A0A0B;            /* 画布 */
  --surface:#141417;       /* 卡片 */
  --surface-2:#1A1B1E;     /* 次级面 / 输入框 */
  /* 文本 */
  --text:#FFFFFF;
  --text-2:#A1A1AA;        /* zinc-400 次要 */
  --text-3:#71717A;        /* zinc-500 弱化 */
  /* 边框 */
  --border:rgba(255,255,255,0.08);
  --border-strong:rgba(255,255,255,0.14);
  /* 唯一强调色（Linear 靛蓝，sat≈55%） */
  --accent:#5E6AD2;
  --accent-hover:#6E7AE2;
  --accent-soft:rgba(94,106,210,0.14);
  /* 语义色 */
  --success:#10B981;
  --warning:#F5A623;
  --error:#FF4D4F;
  /* 圆角 */
  --radius-sm:6px; --radius:10px; --radius-lg:14px;
  /* 间距尺度：4/8/12/16/20/24/32/48/64 */
  /* 阴影 */
  --shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 8px 24px rgba(0,0,0,.4);
  --shadow-lg:0 30px 80px rgba(0,0,0,.45);
  /* 动效 */
  --ease:cubic-bezier(.22,.61,.36,1);
  /* 布局 */
  --wrap:1180px;
}
[data-theme="light"]{
  --bg:#FFFFFF; --surface:#F7F7F8; --surface-2:#FFFFFF;
  --text:#0A0A0B; --text-2:#52525B; --text-3:#71717A;
  --border:rgba(0,0,0,.08); --border-strong:rgba(0,0,0,.14);
  --shadow:0 1px 0 rgba(0,0,0,.03) inset, 0 8px 24px rgba(0,0,0,.08);
  --shadow-lg:0 30px 80px rgba(0,0,0,.12);
}
```

## 字体（系统栈，零下载）
```css
--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
             "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
--font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
```
首屏标题如需拉丁字形更「工程感」，可降级用 `Montserrat`（非强制、不下载）。**禁止 Inter / 任何网络字体。**

## 背景微光（克制，非 AI 光晕）
仅 Hero 用一层极淡的径向靛蓝，透明度 ≤ 0.18，且必须 `→ transparent` 收尾：
```css
background:
  radial-gradient(900px 500px at 78% 8%, rgba(94,106,210,0.18), transparent 60%),
  var(--bg);
```

## 卡片
```css
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:22px;position:relative;overflow:hidden;
  transition:transform .22s var(--ease),border-color .22s ease,box-shadow .22s ease}
.card:hover{transform:translateY(-3px);border-color:var(--border-strong);box-shadow:var(--shadow)}
```

## 按钮
```css
.btn{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 16px;border-radius:var(--radius);
  font-size:14px;font-weight:600;border:1px solid var(--border);color:var(--text);background:var(--surface-2);
  text-decoration:none;cursor:pointer;transition:all .2s var(--ease)}
.btn.primary{background:var(--accent);border-color:transparent;color:#fff}
.btn.primary:hover{background:var(--accent-hover)}
.btn:hover{border-color:var(--border-strong)}
```

## 揭示动效（仅 transform/opacity）
```css
.reveal{opacity:0;transform:translateY(16px);transition:opacity .6s var(--ease),transform .6s var(--ease)}
.reveal.in{opacity:1;transform:none}
@media (prefers-reduced-motion: reduce){.reveal{opacity:1;transform:none;transition:none}}
```
JS：`IntersectionObserver` 给进入视口的 `.reveal` 加 `.in`。
