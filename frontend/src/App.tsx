import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import About from './pages/About'
import Archive from './pages/Archive'
import Home from './pages/Home'
import Results from './pages/Results'
import Search from './pages/Search'

/**
 * 클라이언트 라우팅 (task 19.1, Req 18.1, 18.2).
 * 5개 화면: HOME(/), VISUAL SEARCH(/search), RESULTS(/results),
 * ARCHIVE(/archive), ABOUT(/about). 공통 레이아웃 셸 아래에 중첩한다.
 * BrowserRouter 는 main.tsx 에서 감싼다.
 */
function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="search" element={<Search />} />
        <Route path="results" element={<Results />} />
        <Route path="archive" element={<Archive />} />
        <Route path="about" element={<About />} />
      </Route>
    </Routes>
  )
}

export default App
