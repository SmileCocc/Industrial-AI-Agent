import {createApp} from 'vue'
import {createPinia} from 'pinia'
import {createRouter,createWebHashHistory} from 'vue-router'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './style.css'
import {pages} from './navigation'
import App from './App.vue'
const views = {assistant:()=>import('./views/Assistant.vue'),dashboard:()=>import('./views/Dashboard.vue'),business:()=>import('./views/Business.vue'),system:()=>import('./views/System.vue')}
const routes=pages.map(p=>({path:'/'+p.name,name:p.name,component:p.name==='assistant'?views.assistant:p.name==='dashboard'?views.dashboard:p.group==='生产业务'?views.business:views.system}))
const router=createRouter({history:createWebHashHistory(),routes:[...routes,{path:'/:pathMatch(.*)*',redirect:'/assistant'}]})
router.afterEach(to=>{document.title=`${pages.find(p=>p.name===to.name)?.title ?? '工作台'} | Industrial AI Agent`})
createApp(App).use(createPinia()).use(router).use(ElementPlus,{locale:zhCn}).mount('#app')
