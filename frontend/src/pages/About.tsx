/**
 * ABOUT (`/about`) — 서비스 소개 + Match_Grade 휴리스틱 명시 (Req 11.7, 18.1).
 * Match_Grade(일치도 등급)가 SerpApi 결과의 "유형"(동일 상품 후보 / 유사 상품)과
 * "순위(position)"에 기반한 휴리스틱이며 숫자 점수가 아니라는 점을 명시한다.
 */
function About() {
  return (
    <section className="flex flex-col gap-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tightest md:text-6xl">
          About
        </h1>
        <p className="max-w-2xl text-sm text-text/60 md:text-base">
          CLOSELLER는 사진 한 장으로 비슷하거나 동일한 옷을 파는 페이지를 찾아주는
          비주얼 검색 서비스입니다. 외부 검색은 SerpApi의 Google Lens API만
          사용합니다.
        </p>
      </header>

      <div className="flex flex-col gap-3">
        <h2 className="text-2xl font-bold tracking-tightest md:text-3xl">
          Match_Grade
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-text/70 md:text-base">
          일치도 등급(Match_Grade)은 검색 결과의 <strong>유형</strong>(동일 상품
          후보 / 유사 상품)과 <strong>순위(position)</strong>를 기반으로 한
          휴리스틱으로 산정됩니다. 숫자 점수를 사용하지 않으며 값은 항상 "높음",
          "보통", "낮음" 세 등급 중 하나입니다. 유형·순위 기반 휴리스틱이므로
          실제 일치 정도를 정밀하게 보장하지 않습니다.
        </p>
      </div>
    </section>
  )
}

export default About
