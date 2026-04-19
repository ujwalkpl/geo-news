import { useState } from 'react'
import MapView from './components/MapView'
import Navbar from './components/Navbar'
import Sidebar from './components/Sidebar'

export default function App() {
  const [category, setCategory] = useState(null)
  const [selectedArticles, setSelectedArticles] = useState([])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Navbar category={category} onCategoryChange={setCategory} />
      <MapView category={category} onArticleClick={setSelectedArticles} />
      <Sidebar articles={selectedArticles} onClose={() => setSelectedArticles([])} />
    </div>
  )
}
