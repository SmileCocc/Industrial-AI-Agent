<template>
  <div class="sheet">
    <div class="copy"><span><i/>制造业只读分析</span><h2>从生产现场，<br>找到答案。</h2><p>查询工单、库存与设备，<br>让每个结论都有据可查。</p></div>
    <svg viewBox="0 0 355 240" role="img" aria-label="机械臂与输送线工业线绘" fill="none" stroke-linejoin="round" stroke-linecap="round">
      <g stroke="#75acbf" stroke-width=".8" opacity=".7"><path d="m12 173 125 56 194-99-122-51z M36 187l191-99m-168 109 191-99m-166 109 189-98m-163 110 187-99 M47 154l121 59m-90-75 123 58m-91-73 121 58m-87-75 119 59"/><path d="M82 159V27m-42 68h228" stroke-dasharray="3 5"/></g>
      <g stroke="#afdfed" fill="#174361" stroke-width="1.6">
        <path d="m41 158 40-20 45 19-39 22z M41 158v10l46 21 39-23v-9m-39 22v10"/>
        <ellipse cx="83" cy="149" rx="26" ry="10"/><path d="M61 147v-12q20-17 44-1v15q-22 17-44-2z"/><ellipse cx="83" cy="135" rx="22" ry="9"/>
        <path d="m73 134 8-40 21-32 14 4-20 36-2 33q-12 6-21-1z"/><path d="m89 121 1-22 19-30"/>
        <path d="m99 68 45-36 13 8-39 39z"/><path d="m110 65 36-27"/>
        <path d="m151 32 52 28-2 14-57-28z M154 37l41 22"/>
        <circle cx="109" cy="69" r="11"/><circle cx="109" cy="69" r="5"/><circle cx="150" cy="40" r="10"/><circle cx="150" cy="40" r="4"/>
        <path d="m197 57 13 6-3 18-13-5z M196 77l-7 10 4 6 5-3m6-10 6 10-5 8-4-2"/>
        <path d="m128 162 127-66 62 26-129 69z M128 162v12l60 29 129-69v-12m-129 69v12"/>
        <path v-for="n in 11" :key="n" :d="`m${134+n*10} ${160-n*5.2} 52 23`" stroke-width="1"/>
        <path d="m136 178 1 21 6 3v-21m34 18v20l7 3v-21m113-56v19l6-3v-20"/>
        <path d="m185 130 24-13 25 11-24 14z M185 130v15l25 11 24-13v-15m-24 14v14"/>
      </g>
      <g stroke="#f4c181" stroke-width="1.1"><path d="m225 56 18-16h57M60 126H34l-13-12"/><circle cx="225" cy="56" r="2"/><circle cx="60" cy="126" r="2"/></g>
      <text x="244" y="35" fill="#c8e6ee" font-size="9" font-family="monospace">ROBOT ARM</text>
    </svg>
  </div>
</template>
<style scoped>
.sheet{position:relative;isolation:isolate;display:flex;align-items:center;overflow:hidden;min-height:220px;border-radius:12px;background-color:#123858;background-image:linear-gradient(#83c1da10 1px,transparent 1px),linear-gradient(90deg,#83c1da10 1px,transparent 1px);background-size:19px 19px;color:white}.copy{padding:26px clamp(18px,3vw,38px);z-index:1}.copy span{font-size:12px;color:#cee6f0;display:flex;align-items:center;gap:8px}.copy i{width:15px;height:3px;background:#f4c181}.copy h2{margin:14px 0 10px;font-size:clamp(26px,2.7vw,40px);font-weight:650;line-height:1.22;letter-spacing:-.04em;color:white}.copy p{font-size:13px;line-height:1.65;color:#c1dcea;margin:0}.sheet svg{position:absolute;right:1%;height:98%;width:56%}@container assistant (max-width:520px){.sheet{min-height:190px}.copy{padding:18px}.sheet svg{right:-8%;width:59%}.copy p{font-size:12px}}
</style>
