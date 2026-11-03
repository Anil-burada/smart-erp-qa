'use strict';
const { contextBridge, ipcRenderer } = require('electron');
// Renderer is sandboxed; it receives only these audited methods, not Node.
contextBridge.exposeInMainWorld('smartERPDesktop', Object.freeze({
  openERP: projectId => ipcRenderer.invoke('desktop:open-erp', String(projectId)),
  closeERP: () => ipcRenderer.invoke('desktop:close-erp'),
  setPage: page => ipcRenderer.invoke('desktop:set-page', String(page)),
  startTeaching: () => ipcRenderer.invoke('desktop:teach'),
  navigate: page => ipcRenderer.invoke('desktop:navigate', String(page)),
  status: () => ipcRenderer.invoke('desktop:status'),
  onNavigate: callback => { if (typeof callback === 'function') ipcRenderer.on('desktop:navigate', (_event, page) => callback(page)); },
  onRefresh: callback => { if (typeof callback === 'function') ipcRenderer.on('desktop:refresh', () => callback()); }
}));
