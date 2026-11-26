/**
 * 전역 레이아웃 셸 (base layout shell).
 * 라우팅/5개 화면은 task 19.1 에서 구현한다. 여기서는 토큰·타이포·그레인·
 * 반응형 골격만 적용한다. (Req 18.3, 18.4)
 */
function App() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      {/* 은은한 필름 그레인 오버레이 */}
      <div className="film-grain" aria-hidden="true" />

      <header className="border-b border-surface">
        <div className="mx-auto flex w-full max-w-screen-xl items-center justify-between px-5 py-5 md:px-8">
          <span className="text-xl font-bold tracking-tightest md:text-2xl">
            CLOSELLER.
          </span>
          <nav className="text-xs font-bold uppercase tracking-tightest text-text/60">
            <span className="text-accent">MVP</span>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-screen-xl flex-1 px-5 py-16 md:px-8 md:py-24">
        <h1 className="text-5xl font-bold tracking-tightest md:text-8xl">
          FIND WHAT
          <br />
          THEY WEAR.
        </h1>
      </main>

      <footer className="border-t border-surface">
        <div className="mx-auto flex w-full max-w-screen-xl items-center justify-between px-5 py-6 text-xs uppercase tracking-tightest text-text/50 md:px-8">
          <span>© CLOSELLER</span>
        </div>
      </footer>
    </div>
  )
}

export default App
