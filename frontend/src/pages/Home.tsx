import { Link } from 'react-router-dom'

/**
 * HOME (`/`) — 메인 랜딩/업로드 진입 화면 (Req 18.1).
 * 메인 문구는 design.md 의 "메인 문구(그대로 사용)"를 한 글자도 바꾸지 않고
 * 그대로 표시한다. (번역/수정 금지)
 */
function Home() {
  return (
    <section className="flex flex-col gap-10">
      {/* 메인 문구 — design.md 그대로 */}
      <div className="flex flex-col gap-4">
        <p className="text-sm font-bold uppercase tracking-tightest text-accent md:text-base">
          CLOSELLER.
        </p>
        <h1 className="text-5xl font-bold tracking-tightest md:text-8xl">
          FIND WHAT THEY WEAR.
        </h1>
        <p className="text-base font-bold uppercase tracking-tightest text-text/70 md:text-xl">
          UPLOAD. IDENTIFY. DISCOVER.
        </p>
        <p className="max-w-xl text-sm text-text/60 md:text-base">
          사진 한 장으로 당신이 찾던 옷을 발견하세요.
        </p>
      </div>

      <div>
        <Link
          to="/search"
          className="inline-block border border-accent px-8 py-4 text-sm font-bold uppercase tracking-tightest text-accent transition-colors duration-300 ease-editorial hover:bg-accent hover:text-background"
        >
          Start Visual Search
        </Link>
      </div>
    </section>
  )
}

export default Home
