/**
 * ARCHIVE (`/archive`) — "COMING SOON" 안내만 제공한다 (Req 18.2).
 * 기능은 본 MVP 범위에서 설계·구현하지 않는다.
 */
function Archive() {
  return (
    <section className="flex min-h-[40vh] flex-col items-center justify-center gap-4 text-center">
      <h1 className="text-5xl font-bold tracking-tightest md:text-7xl">
        COMING SOON
      </h1>
      <p className="max-w-md text-sm text-text/50">
        ARCHIVE 기능은 아직 준비 중입니다.
      </p>
    </section>
  )
}

export default Archive
