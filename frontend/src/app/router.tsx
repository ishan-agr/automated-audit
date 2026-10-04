import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { AuditDetailPage } from '@/pages/AuditDetailPage'
import { DashboardPage } from '@/pages/DashboardPage'

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/audits/:auditId', element: <AuditDetailPage /> },
    ],
  },
])
