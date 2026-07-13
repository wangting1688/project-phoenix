/**
 * 图标别名模块 - 将 @element-plus/icons-vue 的导出加上 I 前缀
 * 兼容项目内 IXxx 命名约定的导入
 *
 * 使用方式：import { IPhone, ILock } from '@/utils/icons'
 */
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// 项目中使用的图标列表（导出加上 I 前缀以保持与原代码兼容）
export const IPhone = (ElementPlusIconsVue as any).Phone
export const Iphone = (ElementPlusIconsVue as any).Phone
export const IPhoneFilled = (ElementPlusIconsVue as any).PhoneFilled
export const ILock = (ElementPlusIconsVue as any).Lock
export const IUser = (ElementPlusIconsVue as any).User
export const IUserFilled = (ElementPlusIconsVue as any).UserFilled
export const IUploadFilled = (ElementPlusIconsVue as any).UploadFilled
export const IFolder = (ElementPlusIconsVue as any).Folder
export const IVideoCamera = (ElementPlusIconsVue as any).VideoCamera
export const IFire = (ElementPlusIconsVue as any).Fire
export const IVideoPlay = (ElementPlusIconsVue as any).VideoPlay
export const IEdit = (ElementPlusIconsVue as any).Edit
export const IArrowRight = (ElementPlusIconsVue as any).ArrowRight
export const ILoading = (ElementPlusIconsVue as any).Loading
export const ICopyDocument = (ElementPlusIconsVue as any).CopyDocument
export const ICheck = (ElementPlusIconsVue as any).Check
export const IDocument = (ElementPlusIconsVue as any).Document
export const ISetting = (ElementPlusIconsVue as any).Setting
export const IDataAnalysis = (ElementPlusIconsVue as any).DataAnalysis
export const IHelp = (ElementPlusIconsVue as any).Help
export const IHouse = (ElementPlusIconsVue as any).House
export const IFiles = (ElementPlusIconsVue as any).Files
export const IPicture = (ElementPlusIconsVue as any).Picture
