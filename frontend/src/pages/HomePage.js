import React from "react";
import TurkeyMap from "../components/TurkeyMap";
import { Link } from 'react-router-dom';


const HomePage = () => {
  return (
    <div>
      <h1 style={{ color: '#61dafb', letterSpacing: '3px' }}>TÜRKİYE YATIRIM VE ENERJİ POTANSİYELİ PLATFORMU</h1>
      <TurkeyMap />
      <div style={{
        maxWidth: '900px',
        margin: '40px auto',
        padding: '25px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderRadius: '12px',
        border: '1px solid #444',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
        textAlign: 'left',
        lineHeight: '1.8',
        fontSize: '16px',
        color: 'rgba(255, 255, 255, 0.85)'
      }}>
        <p>
          Türkiye Yatırım ve Enerji Potansiyeli Platformu, Türkiyemizin 81 ili için GYSH verileri ve sektörler özelinde TUİK'ten alınmış verilerle geliştirilmiş bir platformdur. Her bir şehrimizin 2023 yılında ülkemize kazandırdığı hasılatı sektörlere bölerek bir daire grafiği ile göstermektedir. Şehrin coğrafi özellikleri baz alınarak yenilenebilir enerji yatırımı önerisi vermektedir. Sektörlerin zincirlenmiş hacim verileriyle elde edilen 2021-2023 arasındaki reel büyüme verileriyle beraber bir yatırım cazibe skoru hesaplanmış ve bunlara göre yatırım önerileri gerekçeleriyle birlikte verilmiştir.
        </p>
      </div>
    </div>
  );
};

export default HomePage;
