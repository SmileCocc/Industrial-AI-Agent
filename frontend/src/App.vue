<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import {Factory,PanelLeftClose,PanelLeftOpen,ChevronRight,CalendarDays,UserRound,ShieldCheck} from 'lucide-vue-next'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import {pages} from './navigation'
const route=useRoute(), folded=ref(false), mobileOpen=ref(false), online=ref<boolean|null>(null)
const current=computed(()=>pages.find(p=>p.name===route.name) || pages[0]!)
const groups=['工作空间','生产业务','系统管理']
const today=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'long',day:'numeric',weekday:'short'}).format(new Date())
watch(()=>route.name,()=>{mobileOpen.value=false})
onMounted(async()=>{try{const r=await fetch('/health');online.value=r.ok && (await r.json()).status==='ok'}catch{online.value=false}})
function toggle(){ if(window.matchMedia('(max-width: 780px)').matches) mobileOpen.value=!mobileOpen.value; else folded.value=!folded.value }
</script>
<template><ElConfigProvider :locale="zhCn"><div class="shell" :class="{folded,mobileOpen}"><button v-if="mobileOpen" class="nav-overlay" aria-label="关闭菜单" @click="mobileOpen=false"/>
<aside class="rail"><div class="brand"><span class="brand-mark"><Factory :size="26"/></span><div><b>Industrial AI</b><small>制造运营工作台</small></div></div>
<nav><section v-for="g in groups" :key="g"><p>{{g}}</p><router-link v-for="p in pages.filter(x=>x.group===g)" :key="p.name" :to="'/'+p.name" :title="p.title"><component :is="p.icon" :size="18"/><span>{{p.title}}</span></router-link></section></nav>
<div class="rail-footer"><span class="status-lamp" :class="{ok:online}"/><span>Agent {{online===null?'连接中':online?'服务在线':'连接异常'}}</span></div></aside>
<div class="work"><header class="topbar"><button class="nav-toggle" @click="toggle" aria-label="切换导航"><component :is="folded?PanelLeftOpen:PanelLeftClose" :size="18"/></button><div class="crumb">{{current.group}} <ChevronRight :size="13"/> <b>{{current.title}}</b></div><div class="top-end"><span class="date"><CalendarDays :size="15"/>{{today}}</span><span class="operator" title="演示用户"><UserRound :size="16"/></span></div></header>
<main><div class="view-title"><h1>{{current.title}}</h1><span><ShieldCheck :size="15"/> 只读工作区</span></div><RouterView/></main></div></div></ElConfigProvider></template>
