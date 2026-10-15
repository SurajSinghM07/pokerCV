const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('minimize-window'),
  maximize: () => ipcRenderer.send('maximize-window'),
  close: () => ipcRenderer.send('close-window'),
  restartPython: () => ipcRenderer.invoke('restart-python'),
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),
  onPythonLog: (callback) => {
    ipcRenderer.on('python-log', (_, msg) => callback(msg));
  },
  onPythonError: (callback) => {
    ipcRenderer.on('python-error', (_, msg) => callback(msg));
  },
});