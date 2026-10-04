import { ScrollText } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'

export function AppShell() {
  const { pathname } = useLocation()
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-3 px-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <ScrollText className="size-4" />
            </span>
            <span className="text-sm font-semibold tracking-tight">
              Audit<span className="text-muted-foreground">Studio</span>
            </span>
          </Link>
          <nav className="ml-4 flex items-center gap-1 text-sm">
            <NavLink to="/" active={pathname === '/'}>
              Audits
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

function NavLink({
  to,
  active,
  children,
}: {
  to: string
  active: boolean
  children: ReactNode
}) {
  return (
    <Link
      to={to}
      className={cn(
        'rounded-md px-3 py-1.5 transition-colors',
        active
          ? 'bg-accent text-accent-foreground'
          : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {children}
    </Link>
  )
}
