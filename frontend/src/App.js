import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import HomePage from "./pages/HomePage";
import ProvincePage from "./pages/ProvincePage";
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <header className="App-header">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/il/:provinceName" element={<ProvincePage />} />
          </Routes>
        </header>
      </div>
    </Router>
  );
}

export default App;
