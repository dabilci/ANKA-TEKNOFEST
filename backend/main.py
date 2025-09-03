from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import unicodedata
import re

app = FastAPI()

# CORS ayarları
origins = [
    "http://localhost:3000",  # React frontend'in çalıştığı adres
    "http://127.0.0.1:3000",  # Bazı ortamlarda dev server bu origin ile çalışır
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_PATH = Path(__file__).parent.parent / "teknofest tuik"
CITY_IMAGES_PATH = Path(__file__).parent.parent / "cities"

if CITY_IMAGES_PATH.exists():
    app.mount("/cities", StaticFiles(directory=str(CITY_IMAGES_PATH)), name="cities")
CITY_IMAGES_PATH = Path(__file__).parent.parent / "cities"


def _pick_sheet_name(file_path: Path) -> str:
    """Pick a reasonable sheet name if an expected one is not found."""
    xls = pd.ExcelFile(file_path)
    if not xls.sheet_names:
        raise ValueError("Excel dosyasında sayfa bulunamadı")

    prioritized_keywords = ["düzey", "duzey", "trb", "düzey2", "duzey2"]
    for name in xls.sheet_names:
        lname = str(name).lower()
        if any(k in lname for k in prioritized_keywords):
            return name
 
    return xls.sheet_names[0]


def _read_excel_flexible(file_path: Path) -> pd.DataFrame:
    """Read Excel allowing for varying sheet names and header rows."""
    sheet = _pick_sheet_name(file_path)

    try:
        return pd.read_excel(file_path, sheet_name=sheet, header=[4])
    except Exception:
        return pd.read_excel(file_path, sheet_name=sheet, header=0)


def _read_with_header_row(file_path: Path, header_row_index: int = 3) -> pd.DataFrame:
    sheet = _pick_sheet_name(file_path)
    df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None)

    df_raw = df_raw.dropna(axis=0, how='all').dropna(axis=1, how='all')
    if header_row_index >= len(df_raw):
  
        header_row_index = 0
    header = df_raw.iloc[header_row_index].astype(str).apply(lambda x: x.strip())
    df = df_raw.iloc[header_row_index + 1:].copy()
    df.columns = header
    df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')
    df.reset_index(drop=True, inplace=True)
    return df


def _normalize_text(s: str) -> str:
    s = str(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.strip().lower()


def _extract_year(value) -> int | None:

    try:

        if pd.notna(value) and isinstance(value, (int, float)):
            year_int = int(round(float(value)))
            if 1900 <= year_int <= 2100:
                return year_int
    except Exception:
        pass
    try:
        import re
        s = str(value)

        m = re.search(r"(19|20)\d{2}", s)
        if m:
            return int(m.group(0))
    except Exception:
        pass
    return None


def _to_number(value) -> float | None:

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s == "":
        return None

    s = s.replace('%', '').replace('\u00A0', ' ').strip()

    s = s.replace(' ', '')

    if ',' in s and '.' in s:

        s = s.replace('.', '').replace(',', '.')
    else:

        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None

# Lazım olmayan sektörleri atlar
def olmayacak_sector_name(name: str) -> bool:
    n = _normalize_text(name)
    keywords = [
        "yil", "yılı", "yili", "toplam", "sektör toplamı", "sektor toplami",
        "gsyh", "gayrisafi", "genel", "tamamı", "tamami", "vergi", "sübvansiyon", "subvansiyon", "nan"
    ]
    excluded_codes = {"a", "b", "c", "d", "e", "f", "g", "mn", "opq", "o", "p", "q"}
    if any(k in n for k in keywords) or n == "" or n == "nan":
        return True
    if n in excluded_codes:
        return True
    if re.fullmatch(r"[a-z]{1,5}", n) and n.isalpha() and n == n.lower():

        return n in excluded_codes
    return False


@app.get("/")
def read_root():
    return {"message": "Türkiye Yatırım ve Enerji Potansiyeli API"}

@app.get("/gsyh/{il_adi}")
def get_gsyh(il_adi: str):
    try:
        file_path = DATA_PATH / "cari fiyatli .xls"
        # 4. satır başlık (0-based: 3), B=il, C=yıl, D-> sektörler
        df = _read_with_header_row(file_path, header_row_index=3)

        if df.shape[1] < 4:
            return {"error": "Beklenen sütun yapısı bulunamadı (en az 4 sütun)"}

        province_series = df.iloc[:, 1].astype(str)
        year_series = df.iloc[:, 2]

        # İl filtreleme (normalize ederek)
        target = _normalize_text(il_adi)
        il_mask = province_series.apply(_normalize_text) == target
        il_df = df[il_mask].copy()
        
        if il_df.empty:
            return {"error": "İl bulunamadı"}

        # En güncel yılı seç
        il_df["_yil"] = year_series[il_mask].apply(_extract_year)
        il_df = il_df.dropna(subset=["_yil"])  # yıl olmayan satırları at
        if il_df.empty:
            return {"error": "İl için yıl verisi bulunamadı"}
        latest_year = il_df["_yil"].max()
        il_row = il_df[il_df["_yil"] == latest_year].iloc[0:1]

        # Sektör kolonları D sütunundan (index 3) itibaren
        sektor_cols = list(il_row.columns[3:])
        
        # Numerik değerlere indirgeme
        values = []
        for col in sektor_cols:
            sektor_name = str(col).strip()
            if olmayacak_sector_name(sektor_name):
                continue
            raw = il_row.iloc[0][col]
            val = _to_number(raw)
            if val is None:
                continue
            values.append({"sektor": sektor_name, "deger": val})

        return values

    except FileNotFoundError:
        return {"error": "Veri dosyası bulunamadı."}
    except Exception as e:
        return {"error": f"Bir hata oluştu: {str(e)}"}

@app.get("/gsyh_reel/{il_adi}")
def get_gsyh_reel(il_adi: str):
    """
    'zincir hacim.xls' dosyasından yıllık değişim oranlarını okur.
    - Başlıklar 4. satır (0-based index: 3)
    - İl: B sütunu (index 1)
    - Yıl: C sütunu (index 2)
    - Oran sütunları: F, J, N, R, ... (index 5, 9, 13, 17, ...)
    - Sektör adları: D, H, L, P, ... (rate_idx - 2)
    Yalnızca 2021, 2022, 2023 yıllarını döndürür.
    """
    try:
        file_path = DATA_PATH / "zincir hacim.xls"
        sheet = _pick_sheet_name(file_path)
        df = pd.read_excel(file_path, sheet_name=sheet, header=3)

        if df.shape[1] < 6:
            return {"error": "Beklenen sütun yapısı bulunamadı"}

        province_series = df.iloc[:, 1].astype(str)
        target = _normalize_text(il_adi)
        mask = province_series.apply(_normalize_text) == target
        il_df = df[mask].copy()
        if il_df.empty:
            return {"error": "İl bulunamadı"}

        # Sektör adları ve oran sütunları
        sector_cols: list[tuple[int, str]] = []
        for rate_idx in range(5, len(df.columns), 4):
            name_idx = rate_idx - 2
            if name_idx < 0 or name_idx >= len(df.columns):
                continue
            sector_name = str(df.columns[name_idx]).strip()
            if not sector_name or sector_name.lower() == "nan":
                continue
            sector_cols.append((rate_idx, sector_name))

        wanted_years = [2021, 2022, 2023]
        growth_map: Dict[str, Dict[str, float | None]] = {name: {} for _, name in sector_cols}

        for _, row in il_df.iterrows():
            y = _extract_year(row.iloc[2])
            if y not in wanted_years:
                continue
            for rate_idx, sector_name in sector_cols:
                val = _to_number(row.iloc[rate_idx])
                growth_map[sector_name][f"y{y}"] = val if val is not None else None

        buyume_oranlari: List[Dict[str, Any]] = []
        for _, sector_name in sector_cols:
            entry: Dict[str, Any] = {"sektor": sector_name}
            for y in wanted_years:
                entry[f"y{y}"] = growth_map.get(sector_name, {}).get(f"y{y}")
            buyume_oranlari.append(entry)

        return {"years": wanted_years, "reel_hacim": [], "buyume_oranlari": buyume_oranlari}

    except FileNotFoundError:
        return {"error": "Veri dosyası bulunamadı."}
    except Exception as e:
        return {"error": f"Bir hata oluştu: {str(e)}"}


def _build_city_recommendation(il_adi: str) -> Dict[str, Any]:
    core = get_oneriler(il_adi)
    if isinstance(core, dict) and core.get("error"):
        return {"il": il_adi, "error": core["error"]}
    il = core.get("il", il_adi)
    top = core.get("topSectors", [])
    opp = core.get("opportunities", [])
    health = core.get("health", {})

    highlights = []
    for it in top[:3]:
        highlights.append(f"{it.get('sektor')}: skor {round(float(it.get('score', 0))*100):d}%")
    summary = \
        ("Öne çıkan sektörler: " + ", ".join(highlights)) if highlights else "Veri sınırlı."

    # fırsatlardan önerilen actions
    actions = []
    for o in opp:
        title = o.get("title")
        reason = o.get("reason")
        if title and reason:
            actions.append({"title": title, "reason": reason})

    return {
        "il": il,
        "summary": summary,
        "actions": actions,
        "topSectors": top,
        "health": health,
    }


@app.get("/oneriler_tumu")
def get_oneriler_tumu():
    try:
        pop_path = DATA_PATH / "il yaş cinsiyet nufus.xls"
        pdf = pd.read_excel(pop_path, header=None)
        pdf = pdf.dropna(axis=0, how='all').dropna(axis=1, how='all')
        city_row = 2
        start_col = 4
        cities = []
        for cidx in range(start_col, pdf.shape[1]):
            val = pdf.iloc[city_row, cidx] if city_row < len(pdf) and cidx < pdf.shape[1] else None
            if val is None:
                continue
            name = str(val).strip()
            if not name or name.lower() == "nan":
                continue
            cities.append(name)

        seen = set()
        ordered_cities = []
        for c in cities:
            n = _normalize_text(c)
            if n in seen:
                continue
            seen.add(n)
            ordered_cities.append(c)

        payload = [_build_city_recommendation(c) for c in ordered_cities]
        return {"count": len(payload), "items": payload}
    except FileNotFoundError:
        return {"error": "Veri dosyası bulunamadı."}
    except Exception as e:
        return {"error": f"Bir hata oluştu: {str(e)}"}

@app.get("/oneri/{il_adi}")
def get_oneri(il_adi: str):
    """
    'yenilenebilir_enerji_onerileri.xlsx' dosyasında:
    - B: İl
    - C: 1. öneri, D: gerekçe
    - E: 2. öneri, F: gerekçe
    - G: 3. öneri, H: gerekçe
    dökümünü okuyup yapılandırılmış çıktı verir.
    """
    try:
        file_path = DATA_PATH / "yenilenebilir_enerji_onerileri.xlsx"
        # Başlıkları kullanmadan, pozisyonel okuma (B-H) yapalım
        xls = pd.ExcelFile(file_path)
        sheet = xls.sheet_names[0]
        df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None)
        df_raw = df_raw.dropna(axis=0, how='all').dropna(axis=1, how='all')
        # En az 8 sütun olmalı (A-H). Biz B-H kullanacağız → index 1..7
        if df_raw.shape[1] < 8:
            return {"error": "Öneri dosyası beklenen sütun sayısında değil."}

        province_series = df_raw.iloc[:, 1].astype(str)
        target = _normalize_text(il_adi)
        mask = province_series.apply(_normalize_text) == target
        row_df = df_raw[mask]
        if row_df.empty:
            return {"error": "İl için öneri bulunamadı"}

        row = row_df.iloc[0]
        suggestions = []
        # C-D
        suggestions.append({
            "title": str(row.iloc[2]).strip(),
            "reason": str(row.iloc[3]).strip(),
        })
        # E-F
        suggestions.append({
            "title": str(row.iloc[4]).strip(),
            "reason": str(row.iloc[5]).strip(),
        })
        # G-H
        suggestions.append({
            "title": str(row.iloc[6]).strip(),
            "reason": str(row.iloc[7]).strip(),
        })

        return {"il": province_series[mask].iloc[0], "suggestions": suggestions}

    except FileNotFoundError:
        return {"error": "Öneri dosyası bulunamadı."}
    except Exception as e:
        return {"error": f"Bir hata oluştu: {str(e)}"}


@app.get("/oneriler/{il_adi}")
def get_oneriler(il_adi: str):
    """
    Sektör cazibe skorunu hesaplar ve sıralı öneri listesi döner.
    - Hacim (cari fiyatlar, son yıl) → il içindeki pay
    - Trend (reel büyüme, 2021-2023) → 3 yıl ortalaması
    - Skor: 0.5 * minmax(hacim payı) + 0.5 * minmax(ort. reel büyüme)
    Not: Toplam/GSYH/Vergi gibi agregalar hariç tutulur.
    """
    try:
        # 1) Nominal hacimler (cari fiyatlar)
        cari_path = DATA_PATH \
            / "cari fiyatli .xls"
        sheet_cari = _pick_sheet_name(cari_path)
        df_cari_raw = pd.read_excel(cari_path, sheet_name=sheet_cari, header=None)
        df_cari_raw = df_cari_raw.dropna(axis=0, how='all').dropna(axis=1, how='all')
        hdr_idx = 3
        if hdr_idx >= len(df_cari_raw):
            hdr_idx = 0
        cari_header = df_cari_raw.iloc[hdr_idx].astype(str).apply(lambda x: x.strip())
        df_cari = df_cari_raw.iloc[hdr_idx + 1:].copy()
        df_cari.columns = cari_header
        df_cari = df_cari.dropna(axis=0, how='all').dropna(axis=1, how='all')
        df_cari.reset_index(drop=True, inplace=True)

        if df_cari.shape[1] < 4:
            return {"error": "Cari verisi beklenen sütun yapısında değil."}

        target = _normalize_text(il_adi)
        il_mask_cari = df_cari.iloc[:, 1].astype(str).apply(_normalize_text) == target
        il_df_cari = df_cari[il_mask_cari].copy()
        if il_df_cari.empty:
            return {"error": "İl bulunamadı (cari)"}

        il_df_cari["_yil"] = df_cari.iloc[:, 2][il_mask_cari].apply(_extract_year)
        il_df_cari = il_df_cari.dropna(subset=["_yil"])
        if il_df_cari.empty:
            return {"error": "İl için yıl verisi bulunamadı (cari)"}
        latest_year = int(il_df_cari["_yil"].max())
        il_row_cari = il_df_cari[il_df_cari["_yil"] == latest_year].iloc[0]

        nominal_values: dict[str, float] = {}
        for col in list(df_cari.columns[3:]):
            sektor_name = str(col).strip()
            if olmayacak_sector_name(sektor_name):
                continue
            val = _to_number(il_row_cari[col])
            if val is None:
                continue
            nominal_values[sektor_name] = float(val)

        if not nominal_values:
            return {"error": "Sektör nominal verisi bulunamadı"}

        total_nominal = sum(v for v in nominal_values.values() if v is not None)
        if total_nominal <= 0:
            return {"error": "Nominal toplam sıfır veya negatif"}
        nominal_share: dict[str, float] = {
            k: (v / total_nominal) for k, v in nominal_values.items()
        }

        # 2) Reel büyüme (2021-2023)
        reel_path = DATA_PATH / "zincir hacim.xls"
        sheet_reel = _pick_sheet_name(reel_path)
        df_reel = pd.read_excel(reel_path, sheet_name=sheet_reel, header=3)
        if df_reel.shape[1] < 6:
            return {"error": "Reel verisi beklenen sütun yapısında değil."}

        il_mask_reel = df_reel.iloc[:, 1].astype(str).apply(_normalize_text) == target
        il_df_reel = df_reel[il_mask_reel].copy()
        if il_df_reel.empty:
            return {"error": "İl bulunamadı (reel)"}

        # D,H,L,P,... isim; F,J,N,R,... oran
        sector_cols: list[tuple[int, str]] = []
        for rate_idx in range(5, len(df_reel.columns), 4):
            name_idx = rate_idx - 2
            if name_idx < 0 or name_idx >= len(df_reel.columns):
                continue
            sector_name = str(df_reel.columns[name_idx]).strip()
            if not sector_name or sector_name.lower() == "nan":
                continue
            if olmayacak_sector_name(sector_name):
                continue
            sector_cols.append((rate_idx, sector_name))

        wanted_years = [2021, 2022, 2023]
        growth_avg: dict[str, float] = {}
        for rate_idx, sector_name in sector_cols:
            vals: list[float] = []
            for _, row in il_df_reel.iterrows():
                y = _extract_year(row.iloc[2])
                if y not in wanted_years:
                    continue
                val = _to_number(row.iloc[rate_idx])
                if val is not None:
                    vals.append(float(val))
            if vals:
                growth_avg[sector_name] = sum(vals) / len(vals)

        # 3) Ortak sektörler ve skor
        common_sectors = sorted(set(nominal_share.keys()) & set(growth_avg.keys()))
        if not common_sectors:
            return {"error": "Ortak sektör bulunamadı (cari + reel)"}

        def _minmax_scale(values: list[float]) -> list[float]:
            vmin = min(values)
            vmax = max(values)
            if vmax - vmin == 0:
                return [0.5 for _ in values]
            return [(v - vmin) / (vmax - vmin) for v in values]

        shares = [nominal_share[s] for s in common_sectors]
        growths = [growth_avg[s] for s in common_sectors]
        shares_scaled = _minmax_scale(shares)
        growths_scaled = _minmax_scale(growths)

        items = []
        for idx, s in enumerate(common_sectors):
            score = 0.5 * shares_scaled[idx] + 0.5 * growths_scaled[idx]
            items.append({
                "sektor": s,
                "score": round(float(score), 4),
                "nominal_share": round(float(shares[idx]), 6),
                "avg_reel_growth": round(float(growths[idx]), 6),
                "rationale": [
                    f"Hacim payı: {shares[idx]*100:.1f}%",
                    f"Ortalama reel büyüme (2021-2023): {growths[idx]:.2f}%"
                ]
            })

        items.sort(key=lambda x: x["score"], reverse=True)

        # -------------------- Alan bazlı fırsatlar --------------------
        opportunities: list[dict[str, str]] = []

        def _percentile_rank(series_values: list[float], value: float) -> float:
            vals = [v for v in series_values if v is not None]
            if not vals:
                return 0.0
            vals_sorted = sorted(vals)
            import bisect
            pos = bisect.bisect_left(vals_sorted, value)
            return pos / max(1, len(vals_sorted) - 1) if len(vals_sorted) > 1 else 1.0

        # Tarım alanı (A=il, B=toplam alan)
        try:
            tarim_path = DATA_PATH / "toplam tarın alanı.xls"
            tarim_df = pd.read_excel(tarim_path, header=None)
            tarim_df = tarim_df.dropna(axis=0, how='all').dropna(axis=1, how='all')
            tarim_df.columns = [*(f"c{i}" for i in range(len(tarim_df.columns)))]
            tarim_df["_il"] = tarim_df.iloc[:, 0].astype(str)
            tarim_df["_alan"] = pd.to_numeric(tarim_df.iloc[:, 1], errors="coerce")
            tarim_df = tarim_df.dropna(subset=["_alan"])
            tarim_df["_il_norm"] = tarim_df["_il"].apply(_normalize_text)
            il_tarim_row = tarim_df[tarim_df["_il_norm"] == target]
            il_tarim_alan = float(il_tarim_row["_alan"].iloc[0]) if not il_tarim_row.empty else None
            alan_series = [float(x) for x in tarim_df["_alan"].tolist() if pd.notna(x)]
            alan_prc = _percentile_rank(alan_series, il_tarim_alan) if il_tarim_alan is not None else 0.0
        except Exception:
            il_tarim_alan = None
            alan_prc = 0.0

        # İşsizlik (B=il, H=2023)
        try:
            issizlik_path = DATA_PATH / "işsizlik.xls"
            iss_df = pd.read_excel(issizlik_path, header=None)
            iss_df = iss_df.dropna(axis=0, how='all').dropna(axis=1, how='all')
            iss_df["_il"] = iss_df.iloc[:, 1].astype(str)
            iss_df["_rate"] = pd.to_numeric(iss_df.iloc[:, 7], errors="coerce")
            iss_df = iss_df.dropna(subset=["_rate"]) 
            iss_df["_il_norm"] = iss_df["_il"].apply(_normalize_text)
            il_iss = iss_df[iss_df["_il_norm"] == target]
            il_issizlik = float(il_iss["_rate"].iloc[0]) if not il_iss.empty else None
            iss_series = [float(x) for x in iss_df["_rate"].tolist() if pd.notna(x)]
            iss_prc = _percentile_rank(iss_series, il_issizlik) if il_issizlik is not None else 0.0
        except Exception:
            il_issizlik = None
            iss_prc = 0.0

        # Konut satış toplamı 2023 (illere göre konut satış.xls)
        # Şehirler 3. satırda D'den başlar, 2023 ayları 137-148 arası satırlarda; toplamı al
        try:
            konut_path = DATA_PATH / "illere göre konut satış.xls"
            kdf = pd.read_excel(konut_path, header=None)
            kdf = kdf.dropna(axis=0, how='all').dropna(axis=1, how='all')
            # Row indices are 0-based; şehir isimleri 3. satır (index 2), D sütunu (index 3) -> ileri
            city_row_idx = 2
            start_col_idx = 3
            city_names = kdf.iloc[city_row_idx, start_col_idx:]
            city_norms = city_names.astype(str).apply(_normalize_text).tolist()
            try:
                if target in city_norms:
                    city_col_offset = city_norms.index(target)
                    city_col_idx = start_col_idx + city_col_offset
                    # 2023 ay satırları: 137-148 (1-based) => 136-147 (0-based). Toplamını al
                    month_start = 136
                    month_end_inclusive = 147
                    months_series = pd.to_numeric(kdf.iloc[month_start:month_end_inclusive+1, city_col_idx], errors="coerce")
                    il_konut_toplam_2023 = float(months_series.dropna().sum()) if not months_series.dropna().empty else None
                else:
                    il_konut_toplam_2023 = None
            except Exception:
                il_konut_toplam_2023 = None
        except Exception:
            il_konut_toplam_2023 = None

        # Yabancıya konut satış toplamı 2023 (B=il, C=toplam). Her il olmayabilir
        try:
            yabanci_path = DATA_PATH / "illere göre yabancıya konut satış.xls"
            ydf = pd.read_excel(yabanci_path, header=None)
            ydf = ydf.dropna(axis=0, how='all').dropna(axis=1, how='all')
            ydf["_il"] = ydf.iloc[:, 1].astype(str)
            ydf["_toplam"] = pd.to_numeric(ydf.iloc[:, 2], errors="coerce")
            ydf["_il_norm"] = ydf["_il"].apply(_normalize_text)
            yrow = ydf[ydf["_il_norm"] == target]
            il_yabanci_konut_2023 = float(yrow["_toplam"].iloc[0]) if not yrow.empty else None
        except Exception:
            il_yabanci_konut_2023 = None

        # Hastane yatak/sayı verileri kullanılmıyor (talep gereği kaldırıldı)

        # Sağlık personeli detaylı (A=il, B=görev, Y=2023 adet), her il 46 satır blok
        try:
            sp_path = DATA_PATH / "illere göre sağlık personeli.xls"
            sp = pd.read_excel(sp_path, header=None)
            sp["_il"] = sp.iloc[:, 0].astype(str)
            sp["_role"] = sp.iloc[:, 1].astype(str)
            sp["_cnt"] = pd.to_numeric(sp.iloc[:, 24], errors="coerce")
            sp["_il_norm"] = sp["_il"].apply(_normalize_text)

            # A sütunundaki şehir satırından 16 ve 26 satır sonrasını oku
            hekim_toplam = 0.0
            hemsire_toplam = 0.0
            start_idx = None
            for i in range(len(sp)):
                name = str(sp.iloc[i, 0]).strip()
                if _normalize_text(name) == target:
                    start_idx = i
                    break
            if start_idx is not None:
                drow = start_idx + 16
                nrow = start_idx + 26
                if 0 <= drow < len(sp):
                    dv = pd.to_numeric(sp.iloc[drow, 24], errors="coerce")
                    if pd.notna(dv):
                        hekim_toplam = float(dv)
                if 0 <= nrow < len(sp):
                    nv = pd.to_numeric(sp.iloc[nrow, 24], errors="coerce")
                    if pd.notna(nv):
                        hemsire_toplam = float(nv)
            # Diğer kategoriler kullanılmıyor
            ebe_toplam = 0.0
            eczaci_toplam = 0.0
            dis_toplam = 0.0
            diger_toplam = 0.0
        except Exception:
            hekim_toplam = 0.0
            hemsire_toplam = 0.0
            ebe_toplam = 0.0
            eczaci_toplam = 0.0
            dis_toplam = 0.0
            diger_toplam = 0.0

        # Nüfus (şehirler 3. satırda E'den başlar; 4. satırda toplam nüfus)
        try:
            pop_path = DATA_PATH / "il yaş cinsiyet nufus.xls"
            pdf = pd.read_excel(pop_path, header=None)
            pdf = pdf.dropna(axis=0, how='all').dropna(axis=1, how='all')
            city_row = 2
            pop_row = 3
            start_col = 4  # E
            cities_row_vals = pdf.iloc[city_row, start_col:]
            cities_norm = cities_row_vals.astype(str).apply(_normalize_text).tolist()
            if target in cities_norm:
                cidx = start_col + cities_norm.index(target)
                il_nufus_val = pd.to_numeric(pdf.iloc[pop_row, cidx], errors="coerce")
                il_nufus = float(il_nufus_val) if pd.notna(il_nufus_val) else None
            else:
                il_nufus = None
        except Exception:
            il_nufus = None

        # Per-kapita ölçüler ve göreli değerlendirme (yalnızca doktor ve hemşire)
        def _safe_rate(numer: float | None, denom: float | None, scale: float = 1.0) -> float | None:
            if numer is None or denom is None or denom == 0:
                return None
            return float(numer) / float(denom) * scale

        hekim_per_100k = _safe_rate(hekim_toplam, il_nufus, 100000.0)
        hemsire_per_100k = _safe_rate(hemsire_toplam, il_nufus, 100000.0)

        # Sağlık göstergelerini her durumda göster: düşükse 'düşük', değilse 'yeterli'
        def _fmt_health(label: str, val: float | None, threshold: float) -> str:
            if val is None:
                return f"Her 100.000 kişiye düşen {label.lower()} sayısı: veri yok"
            status = "— düşük" if val < threshold else "— yeterli"
            return f"Her 100.000 kişiye düşen {label.lower()} sayısı ≈ {val:.0f} (eşik {int(threshold)}) {status}"

        health_lines = [
            _fmt_health("Doktor", hekim_per_100k, 200.0),
            _fmt_health("Hemşire", hemsire_per_100k, 300.0),
        ]
        
        # Sağlık Fırsatı: SADECE her ikisi birden "yeterli" DEĞİLSE öner.
        doktor_yeterli = hekim_per_100k is not None and hekim_per_100k >= 200.0
        hemsire_yeterli = hemsire_per_100k is not None and hemsire_per_100k >= 300.0

        # Eğer her ikisi de yeterli DEĞİLSE VE en az bir veri varsa (ikisi de None değilse), fırsat vardır.
        if not (doktor_yeterli and hemsire_yeterli):
            if hekim_per_100k is not None or hemsire_per_100k is not None:
                opportunities.append({
                    "title": "Özel sağlık yatırımı",
                    "reason": "; ".join(health_lines)
                })

        # Tarım fırsatı: alan yüksek (>=70p) ve tarım payı düşük (<=40p)
        tarim_share = nominal_share.get("Tarım, ormancılık ve balıkçılık")
        if il_tarim_alan is not None and tarim_share is not None:
            # dağılım için sadece paylar
            share_vals = [nominal_share[s] for s in nominal_share.keys() if "Tarım" in s or "Tarım, ormancılık" in s]
            tarim_share_prc = _percentile_rank(share_vals if share_vals else [tarim_share], tarim_share)
            if alan_prc >= 0.7 and tarim_share_prc <= 0.4:
                opportunities.append({
                    "title": "Tarım işleme & lojistik",
                    "reason": f"Tarım alanı yüksek (>%{int(alan_prc*100)}), tarımsal katma değer payı düşük"
                })

        # Gayrimenkul Fırsatı: Toplam konut satışı 3500'den fazlaysa
        if il_konut_toplam_2023 is not None and il_konut_toplam_2023 > 3500:
            conds = []
            if il_konut_toplam_2023 is not None and il_konut_toplam_2023 > 0:
                conds.append(f"2023 konut satışı toplamı ~{int(il_konut_toplam_2023):,}")
            if il_yabanci_konut_2023 is not None and il_yabanci_konut_2023 > 0:
                conds.append(f"Yabancıya satış ~{int(il_yabanci_konut_2023):,}")
            if conds:
                opportunities.append({
                    "title": "Gayrimenkul Yatırımı",
                    "reason": "; ".join(conds)
                })

        # Turizm Fırsatı: Hizmetler sektörü en cazip 3 sektörden biriyse VEYA yabancıya konut satışı varsa
        is_hizmetler_top_3 = False
        for it in items[:3]:
            if _normalize_text(it.get("sektor", "")) == "hizmetler":
                is_hizmetler_top_3 = True
                break
        
        if is_hizmetler_top_3 or (il_yabanci_konut_2023 is not None and il_yabanci_konut_2023 > 0):
            turizm_reasons = []
            if is_hizmetler_top_3:
                turizm_reasons.append("Hizmetler sektörü yüksek yatırım cazibesine sahip")
            if il_yabanci_konut_2023 is not None and il_yabanci_konut_2023 > 0:
                turizm_reasons.append("Yabancıların bölgeye olan ilgisi yüksek")
            opportunities.append({
                "title": "Turizm ve deneyim ekonomisi",
                "reason": "; ".join(turizm_reasons)
            })

        # Fırsatlara dayalı derinlemesine yatırım önerisi
        
        top_sector_name = items[0]['sektor'] if items else "belirlenen sektörler"
        narrative_headline = f"{il_adi} için {top_sector_name} Odaklı Büyüme Stratejisi"
        
        rationale_parts: list[str] = []
        narrative_actions: list[str] = []
        seen_actions = set()

        def add_unique_action(text):
            if text and text.lower() not in seen_actions:
                narrative_actions.append(text.strip())
                seen_actions.add(text.lower())

        
        # 1. Öne çıkan sektörlerden 5 tane öneri üret
        sector_actions: list[str] = []
        sector_rationale_parts: list[str] = []
        
        def add_sector_action(text: str, rationale: str):
            if len(sector_actions) < 5 and text and text.lower() not in {a.lower() for a in sector_actions}:
                sector_actions.append(text.strip())
                if rationale and rationale not in sector_rationale_parts:
                    sector_rationale_parts.append(rationale)

        for item in items:
            if len(sector_actions) >= 5:
                break
            
            sektor = _normalize_text(item.get("sektor", ""))
            
            if "imalat" in sektor or "sanayi" in sektor:
                r = "Sanayi ve imalat, ilin ekonomik yapısındaki merkezi rolüyle yeni yatırımlar için sağlam bir zemin sunmaktadır."
                add_sector_action("OSB'lerde teknoloji odaklı modernizasyon ve kapasite artışı yatırımları yapın.", r)
                add_sector_action("İhracat potansiyeli yüksek ürün gruplarına yönelik yeni üretim hatları kurun.", r)

            elif "tarim" in sektor or "tarım" in sektor:
                r = "Tarım sektörü, ilin coğrafi avantajları ve potansiyeliyle katma değerli üretim için önemli fırsatlar barındırmaktadır."
                add_sector_action("Tarımsal ürünlerin işlenmesi, paketlenmesi ve markalaşması için modern tesisler kurun.", r)
                add_sector_action("Akıllı tarım ve modern sulama teknolojileriyle birim alandan alınan verimi artırın.", r)

            elif "kamu" in sektor or "eğitim" in sektor:
                r = "Kamu ve eğitim hizmetlerindeki yoğunluk, bu sektörlere hizmet sunan özel sektör girişimleri için önemli bir pazar oluşturmaktadır."
                add_sector_action("Özel eğitim kurumları (kolej, kurs merkezi) açarak eğitim altyapısını destekleyin.", r)

            elif "hizmetler" in sektor:
                 if any("turizm" in o['title'].lower() for o in opportunities):
                    r = "Bölgenin doğal ve kültürel zenginlikleri, turizm ve buna bağlı hizmet sektörlerinde katma değerli yatırımlar için benzersiz bir ortam sunmaktadır."
                    add_sector_action("Bölgenin kimliğine uygun turizm alanlarında yatırım yapın.", r)
                    add_sector_action("Otel tesislerinin kalitesini artırın ve dijital pazarlama ile uluslararası pazarlara açılın.", r)
                 else:
                    r = "Perakende, lojistik ve iş hizmetlerindeki canlılık, şehir ekonomisinin dinamizmini göstermekte ve verimlilik odaklı yatırımlar için potansiyel sunmaktadır."
                    add_sector_action("Şehir içi lojistik hizmetlerini optimize edin.", r)

            elif "gayrimenkul" in sektor or "inşaat" in sektor:
                r = "Bölgedeki kentsel gelişim ve güçlü talep, inşaat ve gayrimenkul sektörlerini cazip kılmaktadır."
                add_sector_action("Enerji verimli ve sürdürülebilir yeşil bina konseptiyle konut projeleri geliştirin.", r)
                add_sector_action("Tesis yönetimi ve profesyonel gayrimenkul danışmanlığı hizmetleri sunun.", r)
        
        # Ana listeleri ve gerekçeleri oluştur
        narrative_actions = sector_actions
        rationale_parts = sector_rationale_parts
        seen_actions = {a.lower() for a in narrative_actions}

        opportunity_titles = {o['title'] for o in opportunities}

        if "Gayrimenkul Yatırımı" in opportunity_titles:
            rationale_parts.append("Ayrıca, bölgedeki canlı konut piyasası ve güçlü talep, gayrimenkul geliştirme alanında ek fırsatlar sunmaktadır.")
            add_unique_action("Artan talebi karşılamaya yönelik gayrimenkul ve inşaat projeleri geliştirin.")
            # Yabancıya satış 500'den fazlaysa ek öneri ver
            if il_yabanci_konut_2023 is not None and il_yabanci_konut_2023 > 500:
                add_unique_action("Yabancı yatırımcılara yönelik kiralama ve mülk yönetimi hizmetleri sunarak pazarı genişletin.")
        
        if "Özel sağlık yatırımı" in opportunity_titles:
            rationale_parts.append("Sağlık altyapısındaki kapasite ihtiyacı, özel sağlık hizmetleri alanında önemli bir yatırım potansiyeli barındırmaktadır.")
            add_unique_action("Nitelikli sağlık hizmeti sunacak özel hastane veya klinikler kurarak kapasite açığını kapatın.")
            add_unique_action("Gerekli işe alımları yaparak sağlık altyapısını güçlendirin.")

        # Eğer hiçbir öneri üretilemediyse, genel bir mesaj ekle
        if not rationale_parts:
            rationale_parts.append(f"{il_adi} ekonomisi, {top_sector_name} sektörünün öncülüğünde çeşitlenmiş bir büyüme potansiyeli sergilemektedir. Belirlenen stratejik alanlara yapılacak yatırımlar, bölgesel kalkınmayı hızlandıracaktır.")
        if not narrative_actions:
            add_unique_action("Pazar araştırması yaparak ilin spesifik ihtiyaçlarına yönelik iş modelleri geliştirin.")
            add_unique_action("Yerel işgücü niteliğini artırmaya yönelik mesleki eğitim programlarına yatırım yapın.")

        # Cümleleri nokta ile bitirerek tek paragraf haline getir
        sentences: list[str] = []
        seen = set()
        for part in rationale_parts:
            txt = str(part).strip()
            if not txt:
                continue
            key = txt.lower()
            if key in seen:
                continue
            seen.add(key)
            if not txt.endswith("."):
                txt += "."
            sentences.append(txt)

        recommendation = {
            "headline": narrative_headline or "İl için potansiyel sektör odaklı yatırım planı",
            "rationale": " ".join(sentences),
            "actions": narrative_actions,
        }

        formula_note = (
            "Skor = 0.5×min-max(hacim payı) + 0.5×min-max(2021-2023 ort. reel büyüme). "
            "Toplam/GSYH/Vergi gibi agregalar hariç tutulur."
        )

        return {
            "il": il_adi,
            "yil": latest_year,
            "topSectors": items,
            "formulaNote": formula_note,
            "opportunities": opportunities,
            "health": {
                "doctor_per_100k": None if hekim_per_100k is None else round(hekim_per_100k, 2),
                "nurse_per_100k": None if hemsire_per_100k is None else round(hemsire_per_100k, 2)
            },
            "recommendation": recommendation
        }

    except FileNotFoundError:
        return {"error": "Veri dosyası bulunamadı."}
    except Exception as e:
        return {"error": f"Bir hata oluştu: {str(e)}"}


@app.get("/saglik_test")
def saglik_test(il_adi: str | None = None):
    """
    Doktor ve hemşire metrikleri için iller bazında veri mevcudiyet testleri yapar.
    Dönüş: her il için bulunan/bulunamayan parçalar ve nedenleri.
    """
    try:
        pop_map: dict[str, float] = {}
        cities_list: list[str] = []
        try:
            pop_path = DATA_PATH / "il yaş cinsiyet nufus.xls"
            pdf = pd.read_excel(pop_path, header=None)
            pdf = pdf.dropna(axis=0, how='all').dropna(axis=1, how='all')
            city_row = 2
            pop_row = 3
            start_col = 4
            for cidx in range(start_col, pdf.shape[1]):
                city_name = str(pdf.iloc[city_row, cidx]) if city_row < len(pdf) and cidx < pdf.shape[1] else None
                if city_name is None or str(city_name).strip() == "" or str(city_name).strip().lower() == "nan":
                    continue
                ncity = _normalize_text(city_name)
                pop_val = pd.to_numeric(pdf.iloc[pop_row, cidx], errors="coerce") if pop_row < len(pdf) else None
                if pd.notna(pop_val):
                    pop_map[ncity] = float(pop_val)
                    cities_list.append(str(city_name).strip())
        except Exception:
            pass

        # sağlık personeli dosyasını oku
        sp = None
        try:
            sp_path = DATA_PATH / "illere göre sağlık personeli.xls"
            sp = pd.read_excel(sp_path, header=None)
            sp["_il"] = sp.iloc[:, 0].astype(str)
            sp["_role"] = sp.iloc[:, 1].astype(str)
            sp["_cnt"] = pd.to_numeric(sp.iloc[:, 24], errors="coerce")
            sp["_il_norm"] = sp["_il"].apply(_normalize_text)
        except Exception:
            sp = None

        # sağlık personeli dosyasından şehirleri oku
        derived_cities: list[str] = []
        if sp is not None:
            prev_city_norm = None
            for i in range(len(sp)):
                raw = sp.iloc[i, 0]
                if raw is None:
                    continue
                name = str(raw).strip()
                if not name or name.lower() == "nan":
                    continue
                cname = _normalize_text(name)
                if cname != prev_city_norm:
                    derived_cities.append(name)
                    prev_city_norm = cname
        if derived_cities:
            cities_list = derived_cities

        # Ofsete göre satır okuma: A sütununda şehir satırını bul → +16 ve +26 satır

        results: list[dict[str, object]] = []
        for city in cities_list:
            if il_adi is not None and _normalize_text(city) != _normalize_text(il_adi):
                continue
            ncity = _normalize_text(city)
            reasons: list[str] = []
            pop = pop_map.get(ncity)
            if pop is None:
                reasons.append("Nüfus verisi bulunamadı")

            doctor_total = None
            nurse_total = None
            if sp is None:
                reasons.append("Sağlık personeli dosyası okunamadı")
            else:
                sidx = None
                for i in range(len(sp)):
                    raw = sp.iloc[i, 0]
                    if raw is None:
                        continue
                    if _normalize_text(str(raw)) == ncity:
                        sidx = i
                        break
                if sidx is None:
                    reasons.append("Şehir satırı bulunamadı (A sütunu)")
                else:
                    drow = sidx + 16
                    nrow = sidx + 26
                    if 0 <= drow < len(sp):
                        dv = pd.to_numeric(sp.iloc[drow, 24], errors="coerce")
                        if pd.notna(dv):
                            doctor_total = float(dv)
                    if 0 <= nrow < len(sp):
                        nv = pd.to_numeric(sp.iloc[nrow, 24], errors="coerce")
                        if pd.notna(nv):
                            nurse_total = float(nv)
                if doctor_total is None:
                    reasons.append("Doktor (TOPLAM HEKİM) hücresi okunamadı")
                if nurse_total is None:
                    reasons.append("Hemşire hücresi okunamadı")

            doctor_per_100k = (doctor_total / pop * 100000.0) if (doctor_total is not None and pop and pop > 0) else None
            nurse_per_100k = (nurse_total / pop * 100000.0) if (nurse_total is not None and pop and pop > 0) else None

            results.append({
                "il": city,
                "population": pop,
                "doctor_total": doctor_total,
                "nurse_total": nurse_total,
                "doctor_per_100k": None if doctor_per_100k is None else round(doctor_per_100k, 2),
                "nurse_per_100k": None if nurse_per_100k is None else round(nurse_per_100k, 2),
                "has_doctor": doctor_total is not None,
                "has_nurse": nurse_total is not None,
                "reasons": reasons,
            })

        # özet sayılar
        summary = {
            "total": len(results),
            "missing_doctor": sum(1 for r in results if r.get("doctor_total") is None),
            "missing_nurse": sum(1 for r in results if r.get("nurse_total") is None),
            "missing_population": sum(1 for r in results if r.get("population") in (None, 0)),
        }

        return {"summary": summary, "results": results}

    except FileNotFoundError:
        return {"error": "Veri dosyası bulunamadı."}
    except Exception as e:
        return {"error": f"Bir hata oluştu: {str(e)}"}
