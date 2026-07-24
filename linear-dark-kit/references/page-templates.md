# 章节模板（复制即用）

每个片段都依赖 `design-tokens.md` 的 `:root` 变量。把它们按顺序拼进 `assets/template.html` 的 `<main>` 即可。

---

## 1. 导航 / Header（毛玻璃吸顶）
```html
<header class="nav reveal">
  <div class="wrap nav-in">
    <a class="brand" href="#">
      <svg class="brand-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 4 7l8 5 8-5-8-5Z"/><path d="m4 12 8 5 8-5M4 17l8 5 8-5"/></svg>
      <span>nano-tools</span>
    </a>
    <nav class="nav-links">
      <a href="#tools">工具</a><a href="#features">特性</a><a href="#stats">数据</a><a href="#faq">文档</a>
    </nav>
    <div class="nav-actions">
      <button class="icon-btn" id="themeToggle" aria-label="切换主题">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
      <a class="btn primary" href="https://github.com/wangzifan396-wzf" target="_blank" rel="noopener">GitHub</a>
    </div>
  </div>
</header>
```
```css
.nav{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 80%,transparent);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--border)}
.nav-in{display:flex;align-items:center;justify-content:space-between;height:62px}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;color:var(--text);text-decoration:none;font-size:15px}
.brand-mark{width:22px;height:22px;color:var(--accent)}
.nav-links{display:flex;gap:26px}
.nav-links a{color:var(--text-2);text-decoration:none;font-size:14px}
.nav-links a:hover{color:var(--text)}
.nav-actions{display:flex;align-items:center;gap:10px}
.icon-btn{width:36px;height:36px;border-radius:var(--radius);border:1px solid var(--border);
  background:var(--surface-2);color:var(--text-2);display:grid;place-items:center;cursor:pointer}
.icon-btn svg{width:18px;height:18px}
.icon-btn:hover{color:var(--accent);border-color:var(--border-strong)}
```

## 2. 非对称 Hero（左文 + 右浏览器预览 mockup）
```html
<section class="hero reveal">
  <div class="wrap hero-in">
    <div class="hero-left">
      <span class="eyebrow">开源 · 零依赖 · 单文件</span>
      <h1 class="title">一个标签页，<br>收纳你全部的开发者工具</h1>
      <p class="subtitle">13 款单文件、离线优先的开发者工具。双击即开，关掉即走，数据不出本机。</p>
      <div class="hero-cta">
        <a class="btn primary" href="#tools">浏览工具</a>
        <a class="btn" href="https://github.com/wangzifan396-wzf" target="_blank" rel="noopener">在 GitHub 查看</a>
      </div>
      <div class="hero-meta"><span><b>13</b> 工具</span><span><b>0</b> 依赖</span><span><b>100%</b> 开源</span></div>
    </div>
    <div class="hero-right">
      <div class="mock" aria-hidden="true">
        <div class="mock-bar"><i></i><i></i><i></i><span class="mock-url">nano-tools · wangzifan396-wzf.github.io</span></div>
        <div class="mock-body" id="mockTiles"></div>
      </div>
    </div>
  </div>
</section>
```
```css
.hero{padding:84px 0 64px;background:radial-gradient(900px 500px at 78% 8%,rgba(94,106,210,0.18),transparent 60%),var(--bg)}
.hero-in{display:flex;align-items:center;gap:48px}
.hero-left{flex:1;max-width:560px}
.eyebrow{display:inline-block;font-family:var(--font-mono);font-size:12px;letter-spacing:.04em;
  color:var(--accent);background:var(--accent-soft);border:1px solid var(--border);padding:5px 10px;border-radius:999px;margin-bottom:18px}
.title{font-size:clamp(34px,4.6vw,52px);font-weight:800;letter-spacing:-.04em;line-height:1.08;margin-bottom:20px}
.subtitle{font-size:clamp(15px,1.6vw,17px);color:var(--text-2);max-width:520px;margin-bottom:30px}
.hero-cta{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:26px}
.hero-meta{display:flex;gap:22px;flex-wrap:wrap;font-size:13px;color:var(--text-3)}
.hero-meta b{color:var(--text);font-weight:700}
.hero-right{flex:1;display:flex;justify-content:center}
.mock{background:var(--surface);border:1px solid var(--border-strong);border-radius:var(--radius-lg);overflow:hidden;box-shadow:var(--shadow-lg);
  transform:perspective(1200px) rotateY(-7deg) rotateX(2deg);transition:transform .5s var(--ease);width:100%;max-width:520px}
.mock:hover{transform:perspective(1200px) rotateY(0) rotateX(0)}
.mock-bar{display:flex;align-items:center;gap:7px;padding:12px 14px;border-bottom:1px solid var(--border);background:var(--surface-2)}
.mock-bar i{width:11px;height:11px;border-radius:50%;background:#3A3B3F;display:inline-block}
.mock-bar i:nth-child(1){background:#FF5F57}.mock-bar i:nth-child(2){background:#FEBC2E}.mock-bar i:nth-child(3){background:#28C840}
.mock-url{flex:1;margin-left:10px;height:24px;border-radius:6px;background:var(--bg);border:1px solid var(--border);
  display:flex;align-items:center;padding:0 10px;font-size:11.5px;color:var(--text-3);font-family:var(--font-mono);overflow:hidden;white-space:nowrap}
.mock-body{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:16px}
.mock-card{background:var(--bg);border:1px solid var(--border);border-radius:9px;padding:12px;display:flex;flex-direction:column;gap:8px}
.m-ico{color:var(--accent)}.m-ico svg{width:16px;height:16px}
.m-t{font-size:12px;color:var(--text);font-weight:600}
.m-l{height:6px;border-radius:3px;background:var(--surface-2)}.m-l.s{width:60%}
@media(max-width:860px){.hero-in{flex-direction:column}.mock{transform:none}}
```

## 3. 三大卖点 / 步骤
```html
<section id="features"><div class="wrap why-grid reveal">
  <div class="why-left">
    <span class="label">为什么选择</span>
    <h2 class="sec-title">告别工具链地狱，回归开发本身</h2>
    <p class="sec-desc">不再为小任务安装笨重软件。每个工具都是一个独立的 index.html——双击即开，关掉即走。</p>
  </div>
  <div class="steps">
    <div class="step"><div class="num a">1</div><div><h3>打开即用</h3><p>无需安装、构建或登录，浏览器直接打开就能干活。</p></div></div>
    <div class="step"><div class="num b">2</div><div><h3>本地优先</h3><p>所有计算在本地完成，文件不上传、数据不出机。</p></div></div>
    <div class="step"><div class="num c">3</div><div><h3>单文件可携</h3><p>每个工具只有一个 HTML 文件，零依赖、可随意复制分享。</p></div></div>
  </div>
</div></section>
```
```css
.why-grid{display:flex;gap:56px;align-items:center;padding:72px 0}
.why-left{flex:1}
.label{display:block;color:var(--accent);font-size:13px;font-weight:700;letter-spacing:.04em;margin-bottom:12px}
.sec-title{font-size:clamp(24px,3vw,32px);font-weight:700;letter-spacing:-.02em;margin-bottom:14px}
.sec-desc{color:var(--text-2);font-size:15px;max-width:460px}
.steps{flex:1;display:flex;flex-direction:column;gap:14px}
.step{display:flex;gap:16px;padding:18px 20px;border-radius:12px;background:var(--surface);border:1px solid var(--border);align-items:center}
.step .num{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-weight:700;color:#fff;flex:none}
.step .num.a{background:var(--accent)}.step .num.b{background:var(--success)}.step .num.c{background:var(--warning)}
.step h3{font-size:15px;margin-bottom:3px}.step p{font-size:13.5px;color:var(--text-2)}
@media(max-width:860px){.why-grid{flex-direction:column;gap:32px}}
```

## 4. 工具网格（SVG 图标 + 角标 + 搜索/筛选）
```html
<section id="tools"><div class="wrap">
  <div class="sec-head reveal"><span class="label">工具矩阵</span>
    <h2 class="sec-title">13 款精心打磨的开发者工具</h2>
    <p class="sec-desc">搜索或按分类筛选，点击「在线试用」立即体验。</p></div>
  <div class="controls reveal">
    <div class="search"><span class="si">⌕</span><input id="search" placeholder="搜索工具…"></div>
    <div class="filters" id="filters"></div>
  </div>
  <div class="grid" id="grid"></div>
</div></section>
```
```css
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;padding:8px 0 40px}
.card-ico{width:46px;height:46px;border-radius:11px;flex:none;display:grid;place-items:center;color:var(--text-2);background:var(--surface-2);border:1px solid var(--border)}
.card-ico svg{width:24px;height:24px}
.card:hover .card-ico{color:var(--accent)}
.card .badge{position:absolute;top:15px;right:15px;z-index:1;font-size:10.5px;font-weight:700;letter-spacing:.04em;color:var(--accent);background:var(--accent-soft);border:1px solid var(--border);padding:3px 8px;border-radius:999px}
.card-top{display:flex;align-items:center;gap:13px}
.card-h h3{font-size:16px;margin-bottom:2px}.card-h .cat{font-size:12px;color:var(--text-3)}
.card p{color:var(--text-2);font-size:13.5px;line-height:1.6;margin:0}
.tags{display:flex;flex-wrap:wrap;gap:6px}.tag{font-size:11px;color:var(--text-3);background:var(--surface-2);border:1px solid var(--border);padding:3px 8px;border-radius:6px}
.card-actions{display:flex;gap:8px;margin-top:auto}
.search{display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:0 12px;height:42px;flex:1;max-width:420px}
.search input{background:none;border:none;outline:none;color:var(--text);font-size:14px;width:100%}
.filters{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:13px;color:var(--text-2);background:var(--surface);border:1px solid var(--border);padding:7px 13px;border-radius:999px;cursor:pointer}
.chip.active{background:var(--accent);color:#fff;border-color:transparent}
```
JS 渲染见 `assets/template.html` 与 `references/icons.md` 的 `iconSvg()`。

## 5. 数据背书
```html
<section id="stats"><div class="wrap"><div class="stats-row reveal" id="statsRow">
  <div class="stat"><b>13</b><span>开发者工具</span></div>
  <div class="stat"><b>0</b><span>第三方依赖</span></div>
  <div class="stat"><b>100%</b><span>本地优先</span></div>
  <div class="stat"><b>MIT</b><span>开源协议</span></div>
</div></div></section>
```
```css
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px 0}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:22px;text-align:center}
.stat b{display:block;font-size:30px;font-weight:800;color:var(--accent);letter-spacing:-.02em}
.stat span{font-size:13px;color:var(--text-2)}
@media(max-width:680px){.stats-row{grid-template-columns:repeat(2,1fr)}}
```

## 6. FAQ（原生 details，零 JS）
```html
<section id="faq"><div class="wrap"><div class="sec-head reveal"><span class="label">常见问题</span><h2 class="sec-title">你可能想知道</h2></div>
  <div class="faq reveal" id="faq">
    <details><summary>这些工具需要联网吗？</summary><p>不需要。所有工具都是单文件、本地优先，计算在你的浏览器内完成，数据不上传。</p></details>
    <details><summary>可以离线使用吗？</summary><p>可以。下载 index.html 后断网也能用，适合内网或飞机上。</p></details>
  </div>
</div></section>
```
```css
.faq{max-width:760px;display:flex;flex-direction:column;gap:10px}
.faq details{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:4px 18px}
.faq summary{cursor:pointer;padding:14px 0;font-weight:600;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq details[open] summary{border-bottom:1px solid var(--border);color:var(--accent)}
.faq p{padding:12px 0;color:var(--text-2);font-size:14px;line-height:1.6;margin:0}
```

## 7. 结尾 CTA + 页脚
```html
<section><div class="wrap"><div class="cta-band reveal">
  <h2>准备好收纳你的工具箱了吗？</h2>
  <p>克隆或下载任意一个 index.html，双击即开。</p>
  <a class="btn primary" href="https://github.com/wangzifan396-wzf" target="_blank" rel="noopener">前往 GitHub</a>
</div></div></section>
<footer class="foot"><div class="wrap foot-in">
  <span>nano-tools · 单文件开发者工具矩阵</span>
  <span>MIT License · 本地优先 · 零依赖</span>
</div></footer>
```
```css
.cta-band{background:linear-gradient(180deg,var(--surface),var(--surface-2));border:1px solid var(--border);
  border-radius:var(--radius-lg);padding:48px;text-align:center;box-shadow:var(--shadow)}
.cta-band h2{font-size:26px;margin-bottom:10px}.cta-band p{color:var(--text-2);margin-bottom:22px}
.foot{border-top:1px solid var(--border);padding:24px 0;margin-top:48px}
.foot-in{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;font-size:13px;color:var(--text-3)}
```

## 8. 主题切换 + 揭示（JS）
```js
// 主题
var root=document.documentElement, t=localStorage.getItem('theme');
if(t) root.dataset.theme=t;
else if(matchMedia('(prefers-color-scheme: light)').matches) root.dataset.theme='light';
document.getElementById('themeToggle').onclick=function(){
  root.dataset.theme = root.dataset.theme==='light'?'dark':'light';
  localStorage.setItem('theme', root.dataset.theme);
};
// 揭示
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)e.target.classList.add('in');});},{threshold:.12});
document.querySelectorAll('.reveal').forEach(function(el){io.observe(el);});
```
