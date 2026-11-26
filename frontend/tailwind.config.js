/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Luxury fashion editorial design tokens (design.md / Req 18.3)
      colors: {
        // 배경
        background: '#0A0A0A',
        // 보조 배경(surface)
        surface: '#181818',
        // 글자
        text: '#F5F5F5',
        // 포인트(accent)
        accent: '#C5F277',
      },
      fontFamily: {
        // 큰 볼드, 모노톤 에디토리얼 타이포 — 시스템 산세리프 스택
        sans: [
          '"Helvetica Neue"',
          'Helvetica',
          'Arial',
          '"Apple SD Gothic Neo"',
          '"Noto Sans KR"',
          'system-ui',
          'sans-serif',
        ],
      },
      letterSpacing: {
        // 에디토리얼 헤드라인용 타이트한 자간
        tightest: '-0.04em',
      },
      // 네온/그라데이션/과한 그림자 금지(Req 18.3): 무거운 그림자 토큰을 두지 않는다.
      // 자연스러운 호버 전환(Req 18.4)에만 사용할 은은한 전환.
      transitionTimingFunction: {
        editorial: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
