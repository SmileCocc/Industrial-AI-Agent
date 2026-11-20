import { Bot, ChartNoAxesCombined, ClipboardList, Boxes, Workflow, BellRing, Cable, Wrench, Settings2 } from 'lucide-vue-next'
export const pages = [
  {name:'assistant',title:'AI 智能助手',group:'工作空间',icon:Bot},
  {name:'dashboard',title:'数据驾驶舱',group:'工作空间',icon:ChartNoAxesCombined},
  {name:'orders',title:'生产工单管理',group:'生产业务',icon:ClipboardList},
  {name:'materials',title:'物料库存管理',group:'生产业务',icon:Boxes},
  {name:'lines',title:'生产线管理',group:'生产业务',icon:Workflow},
  {name:'alarms',title:'设备异常管理',group:'生产业务',icon:BellRing},
  {name:'integrations',title:'系统集成管理',group:'系统管理',icon:Cable},
  {name:'tools',title:'Agent 工具管理',group:'系统管理',icon:Wrench},
  {name:'settings',title:'系统配置',group:'系统管理',icon:Settings2},
]
