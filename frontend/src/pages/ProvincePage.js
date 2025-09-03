import React, { useMemo, useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import ReactECharts from "echarts-for-react";
import { cities } from "turkey-map-react/lib/data";

const sectorDetaylari = {
  "Hizmetler": {
    title: "Hizmetler derken nelerden bahsediliyor?",
    details: `Motorlu taşıtların toptan ve perakende ticareti ile onarımı
Toptan ticaret (Motorlu kara taşıtları ve motosikletler hariç)
Perakende ticaret (Motorlu kara taşıtları ve motosikletler hariç) 
Ulaştırma ve depolama 
Kara taşımacılığı ve boru hattı taşımacılığı 
Su yolu taşımacılığı 
Hava yolu taşımacılığı 
Taşımacılık için depolama ve destekleyici faaliyetler 
Posta ve kurye faaliyetleri
Konaklama ve yiyecek hizmeti faaliyetleri
Konaklama/Turizm
Yiyecek ve içecek hizmeti faaliyetleri`
  },
  "Diğer hizmet faaliyetleri": {
    title: "Diğer hizmetler derken nelerden bahsediliyor?",
    details: `Kültür, sanat, eğlence, dinlence ve spor
Yaratıcı sanatlar, gösteri sanatları ve eğlence faaliyetleri
Kütüphaneler, arşivler, müzeler ve diğer kültürel faaliyetler
Kumar ve müşterek bahis faaliyetleri
Spor faaliyetleri, eğlence ve dinlence faaliyetleri
Diğer hizmet faaliyetleri
Bilgisayarların, kişisel eşyaların ve ev eşyalarının onarımı
Diğer hizmet faaliyetleri`
  }
};

const Modal = ({ data, onClose }) => {
  if (!data) return null;
  return (
    <div onClick={onClose} style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        backgroundColor: '#282c34', color: 'white', padding: '24px', borderRadius: '8px',
        width: '90%', maxWidth: '600px', border: '1px solid #444'
      }}>
        <h3 style={{ marginTop: 0 }}>{data.title}</h3>
        <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>{data.details}</p>
        <button onClick={onClose} style={{
          marginTop: '16px', padding: '8px 16px', cursor: 'pointer',
          border: 'none', borderRadius: '4px', backgroundColor: '#61dafb'
        }}>Kapat</button>
      </div>
    </div>
  );
};

const ProvincePage = () => {
  const { provinceName: rawProvince } = useParams();
  const provinceName = decodeURIComponent(rawProvince || "");
  const [gsyhData, setGsyhData] = useState([]);
  const [reelData, setReelData] = useState({ reel_hacim: [], buyume_oranlari: [] });
  const [oneriData, setOneriData] = useState(null);
  const [oneriError, setOneriError] = useState(null);
  const [onerilerData, setOnerilerData] = useState(null);
  const [onerilerError, setOnerilerError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mapImgError, setMapImgError] = useState(false);
  const [modalData, setModalData] = useState(null);


  const formatIntSpaces = (value) => {
    const n = Math.floor(Number(value) || 0);
    return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  };

  const chartHeight = (rowCount) => Math.max(360, (rowCount || 0) * 32);

  const allSectorsSorted = useMemo(() => {
    const sorted = [...(gsyhData || [])].sort((a, b) => (Number(b.deger) || 0) - (Number(a.deger) || 0));
    return sorted.map((x) => ({ ...x, deger: Math.floor(Number(x.deger) || 0) }));
  }, [gsyhData]);

  const pieOption = useMemo(() => {
    if (!allSectorsSorted.length) return {};
    return {
      tooltip: { trigger: 'item', valueFormatter: (v) => formatIntSpaces(v) },
      series: [
        {
          type: 'pie',
          radius: ['58%', '78%'],
          avoidLabelOverlap: true,
          label: { show: false },
          labelLine: { show: false },
          data: allSectorsSorted.map((x) => ({ name: x.sektor, value: x.deger })),
        },
      ],
    };
  }, [allSectorsSorted]);

  const selectedCity = useMemo(() => {
    const normalized = (s) => (s || '').toString().trim().toLowerCase();
    return cities.find((c) => normalized(c.name) === normalized(provinceName));
  }, [provinceName]);

  const imageCandidates = useMemo(() => {
    const trMap = { 'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U', 'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C' };
    const ascii = (provinceName || "").split("").map(ch => trMap[ch] ?? ch).join("")
      .normalize('NFD').replace(/\p{Diacritic}/gu, '');
    const orig = provinceName || "";
    const bases = [ascii, orig].filter(Boolean);
    const suffixes = [
      " Map Chart.png",
      " Map chart.png",
      " map chart.png",
      " MapChart.png",
      " mapchart.png",
    ];
    const urls = [];
    for (const b of bases) {
      for (const s of suffixes) {
        const fileName = `${b}${s}`;
        urls.push(`http://127.0.0.1:8000/cities/${encodeURIComponent(fileName)}`);
      }
    }
    return urls;
  }, [provinceName]);

  const [imgIdx, setImgIdx] = useState(0);
  useEffect(() => { setImgIdx(0); setMapImgError(false); }, [provinceName, imageCandidates.length]);

  const handleSectorClick = (sectorName) => {
    const details = sectorDetaylari[sectorName.trim()];
    if (details) {
      setModalData(details);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const gsyhUrl = `http://127.0.0.1:8000/gsyh/${provinceName}`;
        const reelUrl = `http://127.0.0.1:8000/gsyh_reel/${provinceName}`;
        const oneriUrl = `http://127.0.0.1:8000/oneri/${provinceName}`;
        const onerilerUrl = `http://127.0.0.1:8000/oneriler/${provinceName}`;
        
        const [gsyhRes, reelRes, oneriRes, onerilerRes] = await Promise.all([
          axios.get(gsyhUrl),
          axios.get(reelUrl),
          axios.get(oneriUrl),
          axios.get(onerilerUrl),
        ]);

        if (gsyhRes.data && !gsyhRes.data.error) {
            setGsyhData(gsyhRes.data);
        } else {
            setError(gsyhRes.data.error || "GSYH verisi alınamadı.");
        }

        if (reelRes.data && !reelRes.data.error) {
            setReelData({
              years: reelRes.data.years || [],
              reel_hacim: reelRes.data.reel_hacim || [],
              buyume_oranlari: reelRes.data.buyume_oranlari || [],
            });
        } else if (reelRes.data && reelRes.data.error) {
            setReelData({ years: [], reel_hacim: [], buyume_oranlari: [] });
        }

        if (oneriRes.data && !oneriRes.data.error) {
            setOneriData(oneriRes.data);
            setOneriError(null);
        } else {
            setOneriData(null);
            setOneriError(oneriRes?.data?.error || "Öneri verisi alınamadı.");
        }

        if (onerilerRes.data && !onerilerRes.data.error) {
            setOnerilerData(onerilerRes.data);
            setOnerilerError(null);
        } else {
            setOnerilerData(null);
            setOnerilerError(onerilerRes?.data?.error || "Yatırım önerileri alınamadı.");
        }

      } catch (err) {
        setError("Veri çekme sırasında bir hata oluştu.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [provinceName]);

  const getNominalChartOptions = () => {
    if (!allSectorsSorted.length) return {};
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => formatIntSpaces(v) },
      grid: { left: "22%", right: "6%", bottom: "3%", top: 20, containLabel: true },
      xAxis: { type: "value", boundaryGap: [0, 0.01], axisLabel: { formatter: (val) => formatIntSpaces(val) } },
      yAxis: { type: "category", data: allSectorsSorted.map(item => item.sektor) },
      series: [
        { name: "Hacim (Cari Fiyat)", type: "bar", data: allSectorsSorted.map(item => item.deger), label: { show: false } },
      ],
    };
  };

  const getGrowthChartOptions = () => {
    const growthRaw = reelData?.buyume_oranlari || [];
    if (!growthRaw.length) return {};

    const yearSet = new Set();
    for (const item of growthRaw) {
      Object.keys(item || {}).forEach((k) => {
        if (/^y\d{4}$/.test(k)) {
          yearSet.add(Number(k.slice(1)));
        }
      });
    }
    let years = Array.from(yearSet).filter((n) => !Number.isNaN(n)).sort();

    const isSingleYearShape = years.length === 0 && typeof (growthRaw[0]?.oran) !== 'undefined';
    if (isSingleYearShape) {
      const sorted = [...growthRaw].sort((a, b) => (Number(b.oran) || 0) - (Number(a.oran) || 0));
      return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => `${Math.round(Number(v) || 0)}%` },
        grid: { left: '22%', right: '6%', bottom: '3%', top: 20, containLabel: true },
        xAxis: { type: 'value', axisLabel: { formatter: (v) => `${Math.round(Number(v) || 0)}%` } },
        yAxis: { type: 'category', data: sorted.map((i) => i.sektor) },
        series: [ { name: 'Büyüme Oranı', type: 'bar', data: sorted.map((i) => Math.round(Number(i.oran) || 0)) } ],
      };
    }

    if (!years.length) {
      return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '22%', right: '6%', bottom: '3%', top: 20, containLabel: true },
        xAxis: { type: 'value' },
        yAxis: { type: 'category', data: growthRaw.map((i) => i.sektor) },
        series: [],
      };
    }

    const sectors = growthRaw.map((item) => item.sektor);
    const series = years.map((y) => ({
      name: `${y}`,
      type: 'bar',
      data: growthRaw.map((item) => {
        const key = `y${y}`;
        const val = item && Object.prototype.hasOwnProperty.call(item, key) ? item[key] : null;
        return val == null ? null : Math.round(Number(val) || 0);
      }),
    }));

    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => `${Math.round(Number(v) || 0)}%` },
      legend: { data: years.map((y) => `${y}`) },
      grid: { left: '22%', right: '6%', bottom: '3%', top: 30, containLabel: true },
      xAxis: { type: 'value', axisLabel: { formatter: (v) => `${Math.round(Number(v) || 0)}%` } },
      yAxis: { type: 'category', data: sectors },
      series,
    };
  };

  if (loading) return <p>Yükleniyor...</p>;
  if (error) return <p>Hata: {error}</p>;

  return (
    <div>
      <Modal data={modalData} onClose={() => setModalData(null)} />
      <div style={{ position: 'fixed', top: 16, left: 16, zIndex: 10 }}>
        <Link to="/" style={{ color: 'white' }}>&larr; Haritaya Dön</Link>
      </div>
      {/* Üst: İl harita görseli ve adı */}
      {imageCandidates && imageCandidates.length > 0 && (
        <img
          src={imageCandidates[Math.min(imgIdx, imageCandidates.length - 1)]}
          alt={`${provinceName} harita`}
          style={{ width: 420, maxWidth: '80vw', marginBottom: 8 }}
          onError={() => {
            if (imgIdx < imageCandidates.length - 1) {
              setImgIdx(imgIdx + 1);
            } else {
              setMapImgError(true);
            }
          }}
        />
      )}
      <h2 style={{ letterSpacing: 2, marginTop: 0 }}>{provinceName.toUpperCase()}</h2>

      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'start', gap: '5vw', width: '100%', maxWidth: 1200, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: '1 1 400px' }}>
          <ReactECharts option={pieOption} style={{ width: 360, height: 360 }} />
          <div style={{ textAlign: 'left', marginTop: '32px', alignSelf: 'stretch' }}>
            <p style={{ fontSize: 'small', opacity: 0.8, marginBottom: '16px', textAlign: 'center' }}>(Fiyatlar Bin TL şeklinde verilmiştir.)</p>
            {allSectorsSorted.map((item, idx) => (
              <div
                key={idx}
                onClick={() => handleSectorClick(item.sektor)}
                style={{
                  marginBottom: 10,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  cursor: sectorDetaylari[item.sektor.trim()] ? 'pointer' : 'default',
                  padding: '4px',
                  borderRadius: '4px',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (sectorDetaylari[item.sektor.trim()]) {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <span style={{ display: 'inline-block', width: 10, height: 10, background: '#c62828', borderRadius: 999 }} />
                <div>
                  <div style={{ fontWeight: 700 }}>{item.sektor}</div>
                  <div style={{ fontWeight: 700 }}>{formatIntSpaces(item.deger)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex: '1 1 400px' }}>
          <img src="/renewable.png" alt="Yenilenebilir Enerji İkonu" style={{ width: 360, height: 360, objectFit: 'contain', marginBottom: '16px', display: 'block', margin: '0 auto 16px' }} />
          <h3>Yenilenebilir Enerji Potansiyelleri</h3>
          {oneriData?.suggestions ? (
            <div style={{ textAlign: 'left' }}>
              {oneriData.suggestions.map((s, i) => (
                <div key={i} style={{ marginBottom: 16 }}>
                  <div style={{ fontWeight: 700 }}>{s.title}</div>
                  <div>{s.reason}</div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ textAlign: 'left' }}>{oneriError ? `Öneri verisi alınamadı: ${oneriError}` : 'Öneri verisi bulunamadı.'}</p>
          )}
        </div>
      </div>

      <div style={{ marginTop: 24, width: '100%', maxWidth: 1100 }}>
        <h3>Hacme Göre Sıralama (Cari Fiyatlarla GSYH)</h3>
        <ReactECharts option={getNominalChartOptions()} style={{ height: chartHeight(gsyhData?.length) }} />
      </div>

      <div style={{ marginTop: 24, width: '100%', maxWidth: 1100 }}>
        <h3>Büyüme Oranına Göre Sıralama (Zincirlenmiş Hacim)</h3>
        {reelData?.buyume_oranlari?.length ? (
          <ReactECharts option={getGrowthChartOptions()} style={{ height: chartHeight(reelData?.buyume_oranlari?.length) }} />
        ) : (
          <p>Bu il için reel büyüme oranı verisi bulunamadı.</p>
        )}
      </div>

      {/* Yatırım Fırsatları - alt bölüm */}
      <div style={{ marginTop: 32, width: '100%', maxWidth: 1100 }}>
        <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid #444', borderRadius: 12, padding: 20, boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <h3 style={{ margin: 0 }}>Yatırım Fırsatları</h3>
            {onerilerData?.yil ? (
              <span style={{ fontSize: 12, padding: '4px 10px', borderRadius: 999, background: 'rgba(97,218,251,0.15)', border: '1px solid #61dafb', color: '#61dafb' }}>{`GSYH ${onerilerData.yil}`}</span>
            ) : null}
          </div>
          <div style={{ fontSize: 13, opacity: 0.9, lineHeight: 1.6, marginBottom: 6 }}>
            Sektör cazibe skoru; bugünkü hacim (cari fiyatlar) ile 2021–2023 ortalama reel büyümeyi birlikte değerlendirir.
            Skor yükseldikçe, hem pazar büyüklüğü hem de yakın dönem trendi daha güçlü kabul edilir.
          </div>
          {onerilerData?.formulaNote && (
            <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 16 }}>{onerilerData.formulaNote}</div>
          )}

          {onerilerData?.topSectors || onerilerData?.opportunities ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {Array.isArray(onerilerData?.topSectors) && onerilerData.topSectors.length > 0 && (
                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid #3a3a3a', borderRadius: 10, padding: 16 }}>
                  <div style={{ fontWeight: 700, marginBottom: 12 }}>Öne Çıkan Sektörler</div>
                  {onerilerData.topSectors.map((s, i) => {
                    const score = Number(s.score || 0);
                    const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
                    return (
                      <div key={i} style={{ marginBottom: 14 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ display: 'inline-flex', width: 22, height: 22, borderRadius: 999, alignItems: 'center', justifyContent: 'center', background: '#61dafb', color: '#0b1b22', fontWeight: 700, fontSize: 12 }}>{i + 1}</span>
                            <span style={{ fontWeight: 700 }}>{s.sektor}</span>
                          </div>
                          <span style={{ fontSize: 12, opacity: 0.85 }}>Skor: {pct}%</span>
                        </div>
                        <div style={{ height: 10, background: '#2a2a2a', borderRadius: 999, border: '1px solid #333' }}>
                          <div style={{ width: `${pct}%`, height: '100%', borderRadius: 999, background: 'linear-gradient(90deg, #1de9b6, #2979ff)' }} />
                        </div>
                        {Array.isArray(s.rationale) && s.rationale.length > 0 && (
                          <div style={{ fontSize: 12, opacity: 0.85, marginTop: 6 }}>{s.rationale.join(' • ')}</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {Array.isArray(onerilerData?.opportunities) && onerilerData.opportunities.length > 0 && (
                <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid #3a3a3a', borderRadius: 10, padding: 16 }}>
                  <div style={{ fontWeight: 700, marginBottom: 12 }}>Alan Bazlı Fırsatlar</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10 }}>
                    {onerilerData.opportunities.map((o, i) => (
                      <div key={i} style={{ border: '1px solid #3f3f3f', borderRadius: 10, padding: 12, background: 'rgba(255,255,255,0.02)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span style={{ display: 'inline-block', width: 8, height: 8, background: '#61dafb', borderRadius: 999 }} />
                          <div style={{ fontWeight: 700 }}>{o.title}</div>
                        </div>
                        {typeof o.reason === 'string' ? (
                          o.reason
                            .split(/\s*;\s*|\s*•\s*/)
                            .filter(Boolean)
                            .map((line, idx) => (
                              <div key={idx} style={{ fontSize: 12, opacity: 0.85, marginTop: idx ? 6 : 0 }}>
                                {line}
                              </div>
                            ))
                        ) : (
                          o.reason && <div style={{ fontSize: 12, opacity: 0.85 }}>{o.reason}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p>Bu il için yatırım önerisi bulunamadı.</p>
          )}
          {}
        </div>
      </div>

      {/* Yatırım Önerisi - sayfa en alt (narrative) */}
      <div style={{ marginTop: 32, width: '100%', maxWidth: 1100 }}>
        <h3>Yatırım Önerisi</h3>
        {onerilerData ? (
          <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid #444', borderRadius: 12, padding: 16 }}>
            {/* Başlık */}
            {onerilerData?.recommendation?.headline && (
              <div style={{ fontWeight: 700, marginBottom: 10 }}>{onerilerData.recommendation.headline}</div>
            )}
            {/* Gerekçeler (paragraf) */}
            {typeof onerilerData?.recommendation?.rationale === 'string' && onerilerData.recommendation.rationale.trim().length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Gerekçe</div>
                <div style={{ opacity: 0.9, lineHeight: 1.6 }}>{onerilerData.recommendation.rationale}</div>
              </div>
            )}

            {/* Eylem önerileri */}
            {Array.isArray(onerilerData?.recommendation?.actions) && onerilerData.recommendation.actions.length > 0 ? (
              <div>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Önerilen Adımlar</div>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {onerilerData.recommendation.actions.map((txt, i) => (
                    <li key={i} style={{ marginBottom: 6 }}>{txt}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div>Bu il için özel eylem önerisi bulunamadı.</div>
            )}
          </div>
        ) : (
          <p>Yatırım önerisi verisi alınamadı.</p>
        )}
      </div>
    </div>
  );
};

export default ProvincePage;