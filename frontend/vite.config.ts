import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'

// 直接引入 Element Plus 的子组件模块：主入口会把全部组件注册进安装器，无法摇树。
const kebab=(name:string)=>name.replace(/^El/,'').replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase()
// option、table-column 等子组件随父组件模块导出。
const moduleOf:Record<string,string>={option:'select','table-column':'table'}
const elementPlus=(name:string)=>{
  if(!name.startsWith('El')) return
  const dir=kebab(name), folder=moduleOf[dir]??dir
  return {name,from:`element-plus/es/components/${folder}/index.mjs`,
          sideEffects:`element-plus/es/components/${dir}/style/css.mjs`}
}

// 体积较大的依赖拆成独立分包；Element Plus 按模板用到的组件自动按需引入。
const groups:Record<string,string[]> = {
  charts:['echarts','zrender'], ui:['element-plus','@element-plus'], markdown:['markdown-it','dompurify'],
  icons:['lucide-vue-next'], framework:['vue','vue-router','pinia']}

export default defineConfig({
  plugins:[vue(),Components({resolvers:[elementPlus],dts:false})],
  // charts 分包是 ECharts 的模块化最小体积（约 530 kB），仅在驾驶舱路由按需加载。
  build:{chunkSizeWarningLimit:600,rollupOptions:{output:{manualChunks(id){
    if(!id.includes('node_modules')) return
    return Object.keys(groups).find(name=>groups[name].some(p=>id.includes(`/node_modules/${p}/`)))
  }}}},
  server:{host:'127.0.0.1',port:5173,strictPort:true,proxy:{'/api':'http://127.0.0.1:8000','/health':'http://127.0.0.1:8000'}}
})
