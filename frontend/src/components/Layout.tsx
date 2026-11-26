import { Link, NavLink, Outlet } from 'react-router-dom'

/**
 * 전역 레이아웃 셸 (base layout shell).
 * 토큰·타이포·그레인·반응형 골격(task 2.2)을 유지하고, 상단 내비게이션으로
 * 5개 화면을 연결한다. 각 라우트의 내용은 <Outlet /> 자리에 렌더된다.
 */

const navItems = [
  { to: '/search', label: 'Visual Search' },
  { to: '/results', label: 'Results' },
  { to: '/archive', label: 'Archive' },
  { to: '/about', label: 'About' },
] as const

function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      {/* 은은한 필름 그레인 오버레이 */}
      <div className="film-grain" aria-hidden="true" />

      <header className="border-b border-surface">
        <div className="mx-auto flex w-full max-w-screen-xl items-center justify-between gap-4 px-5 py-5 md:px-8">
          <Link
            to="/"
            className="text-xl font-bold tracking-tightest md:text-2xl"
          >
            CLOSELLER.
          </Link>
          <nav className="flex items-center gap-4 text-xs font-bold uppercase tracking-tightest md:gap-6">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive
                    ? 'text-accent'
                    : 'text-text/60 transition-colors duration-300 ease-editorial hover:text-text'
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-screen-xl flex-1 px-5 py-16 md:px-8 md:py-24">
        <Outlet />
      </main>

      <footer className="border-t border-surface">
        <div className="mx-auto flex w-full max-w-screen-xl items-center justify-between px-5 py-6 text-xs uppercase tracking-tightest text-text/50 md:px-8">
          <span>© CLOSELLER</span>
          <span className="text-accent">MVP</span>
        </div>
      </footer>
    </div>
  )
}

export default Layout
