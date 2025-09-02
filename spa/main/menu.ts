import { Menu, MenuItemConstructorOptions, BrowserWindow, app, shell } from 'electron';

export function createApplicationMenu(mainWindow: BrowserWindow): Menu {
  const isMac = process.platform === 'darwin';

  const template: MenuItemConstructorOptions[] = [
    ...(isMac ? [{
      label: app.getName(),
      submenu: [
        { role: 'about' as const },
        { type: 'separator' as const },
        { role: 'services' as const },
        { type: 'separator' as const },
        { role: 'hide' as const },
        { role: 'hideOthers' as const },
        { role: 'unhide' as const },
        { type: 'separator' as const },
        { role: 'quit' as const }
      ]
    }] : []),
    {
      label: 'File',
      submenu: [
        {
          label: 'New Build',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.send('menu:new-build');
          }
        },
        {
          label: 'Open Spec',
          accelerator: 'CmdOrCtrl+O',
          click: () => {
            mainWindow.webContents.send('menu:open-spec');
          }
        },
        { type: 'separator' },
        {
          label: 'Export Results',
          accelerator: 'CmdOrCtrl+E',
          click: () => {
            mainWindow.webContents.send('menu:export-results');
          }
        },
        { type: 'separator' },
        ...(isMac ? [] : [{ role: 'quit' as const }])
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        ...(isMac ? [
          { role: 'selectAll' as const }
        ] : [
          { role: 'delete' as const },
          { type: 'separator' as const },
          { role: 'selectAll' as const }
        ])
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Tools',
      submenu: [
        {
          label: 'Build Graph',
          click: () => {
            mainWindow.webContents.send('menu:navigate', 'build');
          }
        },
        {
          label: 'Generate Spec',
          click: () => {
            mainWindow.webContents.send('menu:navigate', 'generate-spec');
          }
        },
        {
          label: 'Generate IaC',
          click: () => {
            mainWindow.webContents.send('menu:navigate', 'generate-iac');
          }
        },
        {
          label: 'Visualize',
          click: () => {
            mainWindow.webContents.send('menu:navigate', 'visualize');
          }
        },
        {
          label: 'Threat Model',
          click: () => {
            mainWindow.webContents.send('menu:navigate', 'threat-model');
          }
        },
        { type: 'separator' },
        {
          label: 'Configuration',
          click: () => {
            mainWindow.webContents.send('menu:navigate', 'config');
          }
        }
      ]
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' },
        ...(isMac ? [
          { type: 'separator' as const },
          { role: 'front' as const }
        ] : [])
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Documentation',
          click: async () => {
            await shell.openExternal('https://github.com/your-org/azure-tenant-grapher/docs');
          }
        },
        {
          label: 'Report Issue',
          click: async () => {
            await shell.openExternal('https://github.com/your-org/azure-tenant-grapher/issues');
          }
        },
        { type: 'separator' },
        {
          label: 'View Logs',
          click: () => {
            mainWindow.webContents.send('menu:view-logs');
          }
        },
        {
          label: 'Run Diagnostics',
          click: () => {
            mainWindow.webContents.send('menu:run-diagnostics');
          }
        },
        ...(isMac ? [] : [
          { type: 'separator' as const },
          { role: 'about' as const }
        ])
      ]
    }
  ];

  return Menu.buildFromTemplate(template);
}
