# ---------------------------
# Imports
# ---------------------------
import streamlit as st
import pandas as pd
import numpy as np
import time
import psutil
from io import BytesIO
from openpyxl.utils import get_column_letter
from datetime import datetime
from dotenv import dotenv_values




# ---------------------------
# Helpers
# ---------------------------
def get_safe_sample_size(df, max_rows=3000, min_rows=500):
    mem_available = psutil.virtual_memory().available / (1024 ** 3)
    factor = min(mem_available / 8, 1.0)
    sample_size = int(len(df) * factor)
    sample_size = max(sample_size, min_rows)
    sample_size = min(sample_size, max_rows, len(df))
    return sample_size

# ---------------------------
# Streamlit page config
# ---------------------------
st.set_page_config(page_title="Auto Clustering App", layout="wide")
st.title("✨ Magia segmentacji i marketingu: od danych do inspirujących sloganów ✨")
st.subheader(
    "Generator sloganów ma swoje zasady i gust. Obsługuje odzież. Można spróbować użyć go do elektroniki, kosmetyków i domowych gadżetów, ale próby użycia go do innych rzeczy niż odzież skutkują fochami."
)

# ---------------------------
# Tabs
# ---------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Plik źródłowy Excel",
    "2️⃣ Segmentacja danych", 
    "3️⃣ Produkt dla grup docelowych", 
    "4️⃣ Slogany reklamowe",
    "5️⃣ Instrukcje",
])
# ---------------------------
# Initialize session_state variables
# ---------------------------
for var in [
    'df', 'best_k', 'df_with_clusters', 'df_clusters',
    'uploaded_file_name', 'csv_ready', 'output_full'
]:
    if var not in st.session_state:
        st.session_state[var] = None if var != 'csv_ready' else False
# ======================================
# INITIALIZE SESSION STATE VARIABLES
# ======================================
if "photo_description" not in st.session_state:
    st.session_state.photo_description = None
if "photo_colors" not in st.session_state:
    st.session_state.photo_colors = []
if "photo_products" not in st.session_state:
    st.session_state.photo_products = []
if "photo_id" not in st.session_state:
    st.session_state.photo_id = None
if "temp_image_path" not in st.session_state:
    st.session_state.temp_image_path = None
# ============================================================
# TAB 1: Szablon CSV do pobrania i przesłania
# ============================================================
with tab1:
    st.header("Przeczytaj najpierw instrukcje w ostatniej zakładce")
    st.markdown("### Pobierz szablon i uzupełnij dane klientów ###")
    
    columns = [
        "ID Klienta", "Wiek", "Płeć", "Zakupiony produkt", "Kategoria",
        "Kwota zakupu", "Lokalizacja", "Rozmiar", "Kolor", "Sezon",
        "Rodzaj dostawy", "Zastosowana zniżka", "Użyty kod promocyjny",
        "Poprzednie zakupy", "Metoda płatności", "Częstotliwość zakupów"
    ]
    
    template_df = pd.DataFrame(columns=columns)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name="Szablon")
        worksheet = writer.sheets["Szablon"]
        
        # Auto-adjust column widths based on header if column is empty
        for i, col in enumerate(template_df.columns, 1):
            # Max length of header (since column is empty)
            max_length = len(col) + 2  # +2 for padding
            worksheet.column_dimensions[get_column_letter(i)].width = max_length

    output.seek(0)
    
    st.download_button(
        label="Pobierz szablon Excel",
        data=output,
        file_name="szablon_pliku.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
# ============================================================
# TAB 2: Full Clustering Workflow
# ============================================================
with tab2:
    st.markdown("### Segmentacja danych klientów")

    # ---------------------------
    # File uploader
    # ---------------------------
    uploaded_file = st.file_uploader(
        "📂 Załaduj plik Excel (limit 50 000 wierszy)", 
        type=["xlsx"], 
        key="tab1_excel"
    )

    if uploaded_file:
        if st.session_state.get('uploaded_file_name') != uploaded_file.name:
            st.session_state.uploaded_file_name = uploaded_file.name
            uploaded_file.seek(0)

            with st.spinner("⏳ Trwa weryfikacja pliku..."):
                # First: try to read the file
                try:
                    df = pd.read_excel(uploaded_file, nrows=50000)
                    df.columns = df.columns.str.strip()  # remove extra spaces
                except Exception as e:
                    st.error(f"⚠️ Błąd podczas wczytywania pliku Excel: {e}")
                    st.stop()  # stop if file cannot be read

                # Second: check columns
                if list(df.columns) == columns:
                    st.session_state.df = df
                    st.session_state.best_k = None
                    st.session_state.df_with_clusters = None
                    st.session_state.df_clusters = None
                    st.session_state.csv_ready = False
                    # numeric columns that are not all NaN
                    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if not df[c].isna().all()]
                    st.session_state.numeric_cols = numeric_cols
                    st.session_state.output_full = None
                    st.success("✅ Plik został poprawnie zweryfikowany — struktura zgodna z szablonem.")
                else:
                    st.error("❌ Struktura pliku nie jest zgodna z oficjalnym szablonem.")
                    st.write("📄 **Please upload correct file.**")
                    st.stop()


    # ---------------------------
    # Persistent table placeholder
    # ---------------------------
    if "table_placeholder" not in st.session_state:
        st.session_state.table_placeholder = st.empty()

    if st.session_state.get("df") is not None:
        st.success(f"✅ Załadowano plik: {st.session_state.uploaded_file_name}")
        st.session_state.table_placeholder.dataframe(
            st.session_state.df.head(5),
            use_container_width=True
        )

        # ---------------------------
        # Prepare numeric data
        # ---------------------------
        df = st.session_state.df
        numeric_cols = st.session_state.numeric_cols

        from sklearn.impute import SimpleImputer
        imputer = SimpleImputer(strategy='median')

        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()

        if len(numeric_cols) < 2:
            st.error("⚠️ W danych jest zbyt mało kolumn numerycznych do segmentacji.")
            st.stop()

        # Imputation
        imputer = SimpleImputer(strategy='median')
        df_numeric_array = imputer.fit_transform(df[numeric_cols])

        # Scaling
        scaler = StandardScaler()
        df_numeric_array = scaler.fit_transform(df_numeric_array)

        # Final DataFrame
        df_numeric = pd.DataFrame(df_numeric_array, columns=numeric_cols)

        # ---------------------------
        # Calculate optimal clusters
        # ---------------------------
        calculate_button = st.button("🔍 Oblicz optymalną liczbę segmentów", key="tab2_best_k")
        if calculate_button:
            import logging

            logging.getLogger('pycaret').setLevel(logging.ERROR)

            # Memory-safe sampling
            max_rows = 3000
            df_sample = df_numeric.sample(max_rows, random_state=42) if len(df_numeric) > max_rows else df_numeric.copy()

            X_scaled = StandardScaler().fit_transform(df_sample)

            best_score = -1
            best_k = 2
            with st.spinner("⏳ Obliczam optymalną liczbę segmentów..."):
                # ✅ Move sklearn imports here
                from sklearn.cluster import KMeans
                from sklearn.metrics import silhouette_score
                # progress = st.progress(0)
                for i, k in enumerate(range(2, 11)):
                    try:
                        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                        labels = kmeans.fit_predict(X_scaled)
                        score = silhouette_score(X_scaled, labels)
                        if score > best_score:
                            best_score = score
                            best_k = k
                    except MemoryError:
                        st.warning(f"⚠️ Brak pamięci przy k={k}. Pomijam ten przypadek.")
                        continue
                    # progress.progress((i + 1) / 9)
                    # time.sleep(0.05)

            st.session_state.best_k = best_k
            st.success(f"✅ Najbardziej optymalna liczba segmentów: {best_k}")

    # ---------------------------
    # Run clustering button
    # ---------------------------
    if st.session_state.get('best_k') is not None:
        if st.button("🚀 Uruchom segmentację", key="tab2_run_cluster_btn"):
            import numpy as np
            import pandas as pd
            from datetime import datetime
            from io import BytesIO
            from pycaret.clustering import setup, create_model, assign_model, save_model, load_model, predict_model

            placeholder = st.empty()
            st.session_state.df_with_clusters = None

            with st.spinner("⏳ Uruchamianie segmentacji... proszę czekać..."):
                df_cleaned = st.session_state.df.dropna(axis=1, how='all')
                safe_size = min(3000, len(df_cleaned))
                df_sample = df_cleaned.sample(safe_size, random_state=42)

                numeric_cols_sample = df_sample.select_dtypes(include=[np.number]).columns
                if len(numeric_cols_sample) > 0:
                    df_sample[numeric_cols_sample] = df_sample[numeric_cols_sample].fillna(df_sample[numeric_cols_sample].median())

                session_id = int(datetime.today().strftime("%d%m%Y"))
                clf = setup(
                    data=df_sample,
                    session_id=session_id,
                    normalize=False,
                    html=False,
                    n_jobs=1,
                    log_experiment=False,
                    verbose=False
                )

                kmeans_model = create_model('kmeans', num_clusters=st.session_state.best_k, verbose=False)
                assign_model(kmeans_model)

                model_filename = f"{st.session_state.uploaded_file_name}_pipeline"
                save_model(kmeans_model, model_filename, verbose=False)
                kmeans_pipeline = load_model(model_filename)

                df_full = df_cleaned.copy()
                if len(numeric_cols_sample) > 0:
                    df_full[numeric_cols_sample] = df_full[numeric_cols_sample].fillna(df_full[numeric_cols_sample].median())

                df_with_clusters = predict_model(kmeans_pipeline, data=df_full)

                # Normalize cluster column to 'Cluster' for consistency
                cluster_col_candidates = ['Cluster', 'cluster', 'Cluster_Label', 'Label']
                for col in cluster_col_candidates:
                    if col in df_with_clusters.columns:
                        df_with_clusters.rename(columns={col: 'Cluster'}, inplace=True)
                        break

                st.session_state.df_with_clusters = df_with_clusters

            placeholder.success(
                f"✅ Segmentacja zakończona! Sklasyfikowano {len(df_with_clusters)} wierszy do {st.session_state.best_k} segmentów."
            )

        # ---------------------------
        # Cluster distribution table
        # ---------------------------
        if st.session_state.get('df_with_clusters') is not None:
            df_clusters = st.session_state.df_with_clusters.copy()

            # Ensure Cluster is numeric
            df_clusters['Cluster'] = (
                df_clusters['Cluster']
                .astype(str)
                .str.replace("Cluster", "", regex=False)
                .str.strip()
            )

            df_clusters['Cluster'] = df_clusters['Cluster'].astype(int)

            # Convert to Segment labels
            df_clusters['Segment_display'] = df_clusters['Cluster'].apply(lambda x: f"Segment {int(x)+1}")

            # Create data for table
            cluster_counts = df_clusters['Segment_display'].value_counts().reset_index()
            cluster_counts.columns = ['Segment', 'Liczba rekordów w segmencie']

            # ✅ Title moved above table
            st.write("### 📊 Rozkład segmentów")
            st.dataframe(cluster_counts, use_container_width=True)

            # Save CSV once
            if st.session_state.get('output_full') is None:
                output_full = BytesIO()
                df_clusters.to_csv(output_full, index=False, encoding='utf-8-sig')
                output_full.seek(0)
                st.session_state.output_full = output_full

            st.download_button(
                label="📥 Pobierz pełny plik z segmentami (CSV)",
                data=st.session_state.output_full.getvalue(),
                file_name=f"{st.session_state.get('uploaded_file_name', 'clusters')}_segmenty.csv",
                mime="text/csv",
                key="download_clusters_btn"
            )


            # ---------------------------
            # Generate segment names and descriptions
            # ---------------------------
            import json
            from io import BytesIO
            import pandas as pd
            from openai import OpenAI
            from dotenv import dotenv_values
            import streamlit as st

            # ---------------------------
            # Load OpenAI key from .env or Tab2 session_state
            # ---------------------------
            env = dotenv_values(".env")
            if "openai_key" not in st.session_state:
                st.session_state.openai_key = st.session_state.get("tab2_openai_key") or env.get("OPENAI_API_KEY")

            # Ask user for key if not present
            if not st.session_state.get("openai_key"):
                st.warning("❌ Nie znaleziono klucza OpenAI. Proszę podać własny klucz:")
                if "user_openai_input" not in st.session_state:
                    st.session_state.user_openai_input = ""  # initialize

                user_key = st.text_input(
                    "Twój OpenAI API Key",
                    type="password",
                    key="user_openai_input",
                    value=st.session_state.user_openai_input
                )
                if user_key:
                    st.session_state.openai_key = user_key
                    st.success("✅ Klucz zapisany! Możesz teraz wygenerować segmenty.")

            # ---------------------------
            # Only proceed if cluster data exists and we have a key
            # ---------------------------
            if st.session_state.get('df_with_clusters') is not None and st.session_state.get('openai_key'):

                # Initialize storage in session_state
                if "all_cluster_rows" not in st.session_state:
                    st.session_state.all_cluster_rows = []

                # Button to generate names & descriptions
                generate_clicked = st.button("🧠 Generuj nazwy i opisy segmentów", key="tab2_generate_desc_btn")

                if generate_clicked:
                    # Clear previous results
                    st.session_state.all_cluster_rows = []

                    df_clusters = st.session_state.df_with_clusters.copy()
                    cluster_descriptions = {}
                    optimal_k = st.session_state.get("best_k", 3)
                    openai_client = OpenAI(api_key=st.session_state.openai_key)

                    # ---------------------------
                    # Function to generate clusters
                    # ---------------------------
                    def generate_clusters(df_clusters, cluster_descriptions, optimal_k):
                        for cluster_id in df_clusters['Cluster'].unique():
                            cluster_df = df_clusters[df_clusters['Cluster'] == cluster_id]
                            summary = ""

                            # Summarize cluster columns
                            for col in df_clusters.columns:
                                if col == 'Cluster':
                                    continue
                                value_counts = cluster_df[col].value_counts().head(10)
                                if not value_counts.empty:
                                    value_counts_str = ', '.join([f"{idx}: {cnt}" for idx, cnt in value_counts.items()])
                                    summary += f"{col}: {value_counts_str}\n"
                            cluster_descriptions[cluster_id] = summary

                            # Prepare data for AI
                            cluster_products = cluster_df['Zakupiony produkt'].dropna().unique().tolist()
                            cluster_colors = cluster_df['Kolor'].dropna().unique().tolist()
                            products_str = ', '.join([f'"{p}"' for p in cluster_products])
                            colors_str = ', '.join([f'"{c}"' for c in cluster_colors])
                            optimal_k = st.session_state.best_k
                            prompt_intro = f"""
            Dla klastra {cluster_id} używaj WYŁĄCZNIE poniższych produktów i kolorów:
            Produkty: [{products_str}]
            Kolory: [{colors_str}]
            ❌ NIE dodawaj żadnych innych produktów ani kolorów.
            """

                            prompt_full = f"""
            {prompt_intro}

            Stwórz **DOKŁADNIE {optimal_k} klastrów** (ani mniej, ani więcej).  
            Każdy klaster musi mieć unikalną nazwę i opis w języku polskim, oparty wyłącznie na danych z danego klastra.  
            Nie twórz fikcyjnych ani dodatkowych klastrów ani produktów.

            Kategorie produktów klientów:
            - artykuły gospodarstwa domowego (np. ręczniki, pościel, garnki, patelnie, akcesoria kuchenne, pojemniki, dekoracje do domu),
            - kosmetyki i produkty pielęgnacyjne (np. kremy, perfumy, szampony, makijaż),
            - elektronika i akcesoria (np. słuchawki, sprzęt audio, małe AGD, akcesoria telefoniczne),
            - odzież i dodatki (np. sukienki, spodnie, koszule, buty, torebki, biżuteria).

            ⚠️ W nazwach klastrów nie używaj słów związanych z wiekiem.  
            Nazwy muszą być neutralne, kreatywne i marketingowo atrakcyjne.

            Instrukcje krok po kroku:
            1. Sprawdź produkty i kolory w danym klastrze.
            2. Stwórz nazwę i opis klastra **tylko na podstawie danych z kroku 1**.
            3. Uwzględnij zachowania klientów, preferencje zakupowe, częstotliwość zakupów i formy płatności.
            4. Każdy klaster musi być całkowicie unikalny.
            5. Odpowiedz w formacie JSON zawierającym **dokładnie {optimal_k} klastrów**.

            Przykład:
                {{
                "Segment 0": {{
                    "name": "Miłośnicy elegancji i pielęgnacji",
                    "description": "Klienci skupieni na produktach kosmetycznych i odzieży premium, często kupują kremy, perfumy oraz modne dodatki. Preferują zakupy online i promocje sezonowe. Ulubione kolory to czarny, czerwony i fioletowy."
                }},
                "Segment 1": {{
                    "name": "Tech-entuzjaści i praktyczni domownicy",
                    "description": "Osoby kupujące sprzęt elektroniczny, jak klawiatury i myszy komputerowe. Cenią nowoczesne rozwiązania i produkty łączące funkcjonalność z designem. Ulubione kolory to szary i zielony."
                }}
            }}
            """

                            prompt = prompt_full

                    # ---------------------------
                    # Call OpenAI
                    # ---------------------------
                    try:
                        response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            temperature=0.3,
                            messages=[{"role": "user", "content": prompt}]
                        )

                        # Safe extraction
                        choice = response.choices[0]
                        if hasattr(choice, "message"):
                            result_text = choice.message.content
                        elif hasattr(choice, "text"):
                            result_text = choice.text
                        else:
                            result_text = ""

                        result_text = result_text.replace("```json", "").replace("```", "").strip()

                        try:
                            cluster_json = json.loads(result_text)
                        except json.JSONDecodeError:
                            st.error("❌ Nie udało się sparsować odpowiedzi jako JSON.")
                            st.text(result_text)
                            cluster_json = {}

                        # Build rows
                        for key, val in cluster_json.items():
                            if isinstance(val, dict):
                                name = val.get("name", "")
                                description = val.get("description", "")
                            else:
                                name = ""
                                description = str(val)
                            try:
                                cid = int(str(key).replace("Cluster ", "").strip())
                            except:
                                cid = str(key)
                            st.session_state.all_cluster_rows.append({
                                "Cluster": cid,
                                "Name": name,
                                "Description": description
                            })

                    except Exception as e:
                        st.error(f"❌ Błąd podczas komunikacji z OpenAI: {e}")

            # ---------------------------
            # Run generation with spinner
            # ---------------------------
            with st.spinner("⏳ Generowanie nazw i opisów segmentów... proszę czekać..."):
                generate_clusters(df_clusters, cluster_descriptions, optimal_k)

            if st.session_state.all_cluster_rows:
                st.session_state.df_clusters = pd.DataFrame(st.session_state.all_cluster_rows)
                st.success("✅ Nazwy i opisy segmentów wygenerowane!")

                # Prepare CSV for download
                output_desc = BytesIO()
                st.session_state.df_clusters.to_csv(output_desc, index=False, encoding='utf-8-sig')
                output_desc.seek(0)
                st.session_state.output_desc = output_desc

    # ---------------------------
    # Show cluster descriptions + download
    # ---------------------------
    if st.session_state.get('df_clusters') is not None:
        st.write("### ✅ Nazwy i opisy segmentów")
        df_display = st.session_state.df_clusters.copy()
        df_display.rename(columns={
            "Cluster": "Segment",
            "Name": "Nazwa",
            "Description": "Opis"
        }, inplace=True)
        df_display["Segment"] = df_display["Segment"].apply(
            lambda x: f"Segment {int(x)+1}" if str(x).isdigit() else x
        )
        st.dataframe(df_display, use_container_width=True)

        if st.session_state.get('output_desc') is not None:
            st.download_button(
                label="📥 Pobierz opisy segmentów (CSV)",
                data=st.session_state.output_desc.getvalue(),
                file_name=f"{st.session_state.get('uploaded_file_name', 'clusters')}_opisy_segmentow.csv",
                mime="text/csv",
                key="download_descriptions_btn_unique"
            )


# ============================================================
# TAB 3: Image Analysis (OpenAI)
# ============================================================
with tab3:
    st.markdown("### Analiza zdjęcia produktu")

    from PIL import Image
    import time
    import base64
    from dotenv import dotenv_values
    from openai import OpenAI

    # ---------------------------
    # Initialize OpenAI client using the key from Tab 2 if available
    # ---------------------------
    if "openai_client" not in st.session_state:
        # First try session_state key from Tab 2
        openai_key = st.session_state.get("openai_key")

        # If not available, fallback to .env
        if not openai_key:
            env = dotenv_values(".env")
            openai_key = env.get("OPENAI_API_KEY")

        if openai_key:
            st.session_state["openai_client"] = OpenAI(api_key=openai_key)
        else:
            st.warning("❌ Brak klucza OpenAI. Wprowadź go w Tab 2 lub w pliku .env.")

    # ---------------------------
    # Helper to convert image
    # ---------------------------
    def prepare_image_for_open_ai(image_path):
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        return "data:image/png;base64," + base64.b64encode(img_bytes).decode("utf-8")

    # ---------------------------
    # Upload image
    # ---------------------------
    uploaded_image = st.file_uploader(
        "Prześlij zdjęcie", type=["png", "jpg", "jpeg"], key="tab3_uploader"
    )

    if uploaded_image:
        # jeśli to nowy plik (nazwa inna niż zapisana wcześniej) — zresetuj powiązane dane
        prev_name = st.session_state.get("uploaded_image_name")
        if prev_name != uploaded_image.name:
            st.session_state["photo_description"] = None
            st.session_state["photo_colors"] = []
            st.session_state["photo_products"] = []
            st.session_state["photo_id"] = None
            st.session_state["temp_image_path"] = None

        # zapisz nazwę i tymczasowy plik (nadpisz zawsze aktualnym obiektem uploadera)
        st.session_state["uploaded_image_name"] = uploaded_image.name
        temp_image_path = f"temp_{uploaded_image.name}"
        with open(temp_image_path, "wb") as f:
            f.write(uploaded_image.getbuffer())
        st.session_state["uploaded_image"] = uploaded_image
        st.session_state["temp_image_path"] = temp_image_path

        img = Image.open(temp_image_path)
        img.thumbnail((300, 300))
        st.image(img, caption="Przesłane zdjęcie", use_container_width=False)

    elif st.session_state.get("uploaded_image") and st.session_state.get("temp_image_path"):
        temp_image_path = st.session_state.temp_image_path
        img = Image.open(temp_image_path)
        img.thumbnail((300, 300))
        st.image(img, caption="Przesłane zdjęcie", use_container_width=False)


    # ---------------------------
    # Generate description button
    # ---------------------------
    if st.session_state.get("temp_image_path"):
        if st.button("Generuj opis zdjęcia", key="generate_photo_desc_tab3"):
            openai_client = st.session_state.get("openai_client")
            temp_image_path = st.session_state.get("temp_image_path")

            if openai_client and temp_image_path:
                with st.spinner("📝 Generowanie opisu zdjęcia..."):
                    try:
                        # ---------------------------
                        # OpenAI prompt
                        # ---------------------------
                        prompt_text = f"""
        Stwórz dokładny i atrakcyjny opis przesłanego zdjęcia. Bardzo ważne:
        1️⃣ Pierwsze zdanie musi zaczynać się od: "Na zdjęciu widoczna jest ..." lub "Na zdjęciu widoczny jest..." i naturalnie opisz produkt: materiał, krój, styl. 1-2 zdania.
        2️⃣ Drugie zdanie: Wyraźnie podaj główny kolor produktu w formacie:
        "Głównym kolorem (NAZWA PRODUKTU) jest (NAZWA KOLORU Z DICTIONARY)"
        Produkt musi być w poprawnej formie gramatycznej (singular).
        3️⃣ Kolor musi być jednym z dozwolonych kolorów.
        4️⃣ Zachowaj atrakcyjny, naturalny i marketingowy ton opisu.
        """

                        response = openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            temperature=0,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt_text},
                                    {"type": "image_url", "image_url": {"url": prepare_image_for_open_ai(temp_image_path), "detail": "high"}}
                                ],
                            }]
                        )

                        description = response.choices[0].message.content.strip()
                        st.session_state.photo_description = description

                        # ---------------------------
                        # Detect colors and products
                        # ---------------------------
                        possible_colors = [
                        "szary", "szara", "szare", "szarość",
                        "bordowy", "bordowa", "bordowe",
                        "turkusowy", "turkusowa", "turkusowe",
                        "biały", "biała", "białe",
                        "grafitowy", "grafitowa", "grafitowe",
                        "srebrny", "srebrna", "srebrne", "srebro",
                        "różowy", "różowa", "różowe", "róż",
                        "fioletowy", "fioletowa", "fioletowe", "fiolet",
                        "oliwkowy", "oliwkowa", "oliwkowe",
                        "złoty", "złota", "złote",
                        "turkusowozielony", "turkusowozielona", "turkusowozielone", "morski",
                        "czarny", "czarna", "czarne", "czerń",
                        "zielony", "zielona", "zielone", "zieleń",
                        "brzoskwiniowy", "brzoskwiniowa", "brzoskwiniowe",
                        "czerwony", "czerwona", "czerwone", "czerwień",
                        "cyjanowy", "cyjanowa", "cyjanowe",
                        "brązowy", "brązowa", "brązowe",
                        "beżowy", "beżowa", "beżowe",
                        "pomarańczowy", "pomarańczowa", "pomarańczowe", "pomarańcz",
                        "granatowy", "granatowa", "granatowe",
                        "fuksja", "magenta",
                        "niebieski", "niebieska", "niebieskie",
                        "błękitny", "błękitna", "błękitne",
                        "lawendowy", "lawendowa", "lawendowe",
                        "kremowy", "kremowa", "kremowe",
                        "ecru", "ivory",
                        "khaki", "oliwkowy jasny",
                        "karmelowy", "camel",
                        "burgundowy", "burgundowa", "burgundowe",
                        "miętowy", "miętowa", "miętowe",
                        "dżinsowy", "dżinsowa", "dżinsowe",
                        "wielokolorowy", "wielokolorowa", "wielokolorowe",
                        "żółty", "żółta", "żółte", "żółć"
]

                        product_singular_map = {
                            "sukienka": ["sukienka", "sukienki"],
                            "spodnie": ["spodnie"],
                            "spódnica": ["spódnica", "spódnice"],
                            "bluzka": ["bluzka", "bluzki"],
                            "sweter": ["sweter", "swetry"],
                            "t-shirt": ["t-shirt", "t-shirty"],
                            "koszula": ["koszula", "koszule"],
                            "kurtka": ["kurtka", "kurtki"],
                            "płaszcz": ["płaszcz", "płaszcze"],
                            "marynarka": ["marynarka", "marynarki"],
                            "garnitur": ["garnitur", "garnitury"],
                            "kamizelka": ["kamizelka", "kamizelki"],
                            "kombinezon": ["kombinezon", "kombinezony"],
                            "legginsy": ["legginsy"],
                            "szorty": ["szorty"],
                            "buty": ["but", "buty"],
                            "sandały": ["sandał", "sandały"],
                            "trampki": ["trampka", "trampki"],
                            "kozaki": ["kozak", "kozaki"],
                            "botki": ["botek", "botki"],
                            "szpilki": ["szpilka", "szpilki"],
                            "mokasyny": ["mokasyn", "mokasyny"],
                            "baletki": ["baletka", "baletki"],
                            "kapcie": ["kapcie"],
                            "okulary": ["okulary"],
                            "biżuteria": ["biżuteria"],
                            "naszyjnik": ["naszyjnik", "naszyjniki"],
                            "bransoletka": ["bransoletka", "bransoletki"],
                            "pierścionek": ["pierścionek", "pierścionki"],
                            "kolczyki": ["kolczyk", "kolczyki"],
                            "zegarek": ["zegarek", "zegarki"],
                            "torebka": ["torebka", "torebki"],
                            "plecak": ["plecak", "plecaki"],
                            "portfel": ["portfel", "portfele"],
                            "pasek": ["pasek", "paski"],
                            "szalik": ["szalik", "szaliki"],
                            "apaszka": ["apaszka", "apaszki"],
                            "czapka": ["czapka", "czapki"],
                            "kapelusz": ["kapelusz", "kapelusze"],
                            "rękawiczki": ["rękawiczka", "rękawiczki"],
                            "skarpetki": ["skarpetka", "skarpetki"],
                            "rajstopy": ["rajstopy"],
                            "bielizna": ["bielizna"],
                            "biustonosz": ["biustonosz", "biustonosze"],
                            "majtki": ["majtek", "majtki"],
                            "piżama": ["piżama", "piżamy"],
                            "szlafrok": ["szlafrok", "szlafroki"],
                            "kostium kąpielowy": ["kostium kąpielowy", "kostiumy kąpielowe"],
                            "bikini": ["bikini"],
                            "smartfon": ["smartfon", "smartfony"],
                            "laptop": ["laptop", "laptopy"],
                            "komputer": ["komputer", "komputery"],
                            "tablet": ["tablet", "tablety"],
                            "monitor": ["monitor", "monitory"],
                            "telewizor": ["telewizor", "telewizory"],
                            "drukarka": ["drukarka", "drukarki"],
                            "skaner": ["skaner", "skanery"],
                            "aparat fotograficzny": ["aparat fotograficzny", "aparaty fotograficzne"],
                            "obiektyw": ["obiektyw", "obiektywy"],
                            "głośnik": ["głośnik", "głośniki"],
                            "słuchawki": ["słuchawka", "słuchawki"],
                            "mysz": ["mysz", "mysze"],
                            "klawiatura": ["klawiatura", "klawiatury"],
                            "router": ["router", "routery"],
                            "konsola": ["konsola", "konsole"],
                            "drukarka 3D": ["drukarka 3D", "drukarki 3D"],
                            "powerbank": ["powerbank", "powerbanki"],
                            "ładowarka": ["ładowarka", "ładowarki"],
                            "odtwarzacz": ["odtwarzacz", "odtwarzacze"],
                            "dron": ["dron", "drony"],
                            "kamera": ["kamera", "kamery"],
                            "mebel": ["mebel", "meble"],
                            "sofa": ["sofa", "sofy"],
                            "krzesło": ["krzesło", "krzesła"],
                            "stół": ["stół", "stoły"],
                            "biurko": ["biurko", "biurka"],
                            "szafa": ["szafa", "szafy"],
                            "łóżko": ["łóżko", "łóżka"],
                            "materac": ["materac", "materace"],
                            "dywan": ["dywan", "dywany"],
                            "zasłona": ["zasłona", "zasłony"],
                            "poduszka": ["poduszka", "poduszki"],
                            "pościel": ["pościel"],
                            "lampka": ["lampka", "lampki"],
                            "lustro": ["lustro", "lustra"],
                            "obraz": ["obraz", "obrazy"],
                            "ramka": ["ramka", "ramki"],
                            "świeca": ["świeca", "świece"],
                            "dekoracja": ["dekoracja", "dekoracje"],
                            "zegar": ["zegar", "zegary"],
                            "roślina": ["roślina", "rośliny"],
                            "garnek": ["garnek", "garnki"],
                            "patelnia": ["patelnia", "patelnie"],
                            "brytfanna": ["brytfanna", "brytfanny"],
                            "forma do pieczenia": ["forma do pieczenia", "formy do pieczenia"],
                            "noże kuchenne": ["nóż kuchenny", "noże kuchenne"],
                            "łyżka": ["łyżka", "łyżki"],
                            "widelec": ["widelec", "widelce"],
                            "deska do krojenia": ["deska do krojenia", "deski do krojenia"],
                            "tarka": ["tarka", "tarki"],
                            "czajnik": ["czajnik", "czajniki"],
                            "mikser": ["mikser", "miksery"],
                            "piekarnik": ["piekarnik", "piekarniki"],
                            "mikrofalówka": ["mikrofalówka", "mikrofalówki"],
                            "ekspres do kawy": ["ekspres do kawy", "ekspresy do kawy"],
                            "toster": ["toster", "tostery"],
                            "zmywarka": ["zmywarka", "zmywarki"],
                            "płyta indukcyjna": ["płyta indukcyjna", "płyty indukcyjne"],
                            "talerz": ["talerz", "talerze"],
                            "kubek": ["kubek", "kubki"],
                            "szklanka": ["szklanka", "szklanki"],
                            "kieliszek": ["kieliszek", "kieliszki"],
                            "dzbanek": ["dzbanek", "dzbanki"],
                            "pojemnik": ["pojemnik", "pojemniki"],
                            "termos": ["termos", "termosy"],
                            "chlebak": ["chlebak", "chlebaki"],
                            "ręcznik kuchenny": ["ręcznik kuchenny", "ręczniki kuchenne"],
                            "fartuch": ["fartuch", "fartuchy"],
                            "rękawica": ["rękawica", "rękawice"],
                            "zlew": ["zlew", "zlewy"],
                            "lodówka": ["lodówka", "lodówki"],
                            "zmywak": ["zmywak", "zmywaki"],
                            "podkład": ["podkład", "podkłady"],
                            "korektor": ["korektor", "korektory"],
                            "puder": ["puder", "pudry"],
                            "róż": ["róż", "róże"],
                            "bronzer": ["bronzer", "bronsery"],
                            "rozświetlacz": ["rozświetlacz", "rozświetlacze"],
                            "baza pod makijaż": ["baza pod makijaż", "bazy pod makijaż"],
                            "utrwalacz makijażu": ["utrwalacz makijażu", "utrwalacze makijażu"],
                            "maska do twarzy": ["maska do twarzy", "maski do twarzy"],
                            "krem": ["krem", "kremy"],
                            "serum": ["serum", "sera"],
                            "tonik": ["tonik", "toniki"],
                            "peeling": ["peeling", "peelingi"],
                            "cienie do powiek": ["cień do powiek", "cienie do powiek"],
                            "eyeliner": ["eyeliner", "eyelinery"],
                            "maskara": ["maskara", "maskary"],
                            "baza pod cienie": ["baza pod cienie", "bazy pod cienie"],
                            "żel do brwi": ["żel do brwi", "żele do brwi"],
                            "ołówek do brwi": ["ołówek do brwi", "ołówki do brwi"],
                            "cienie do brwi": ["cień do brwi", "cienie do brwi"],
                            "pomadka": ["pomadka", "pomadki"],
                            "błyszczyk": ["błyszczyk", "błyszczyki"],
                            "konturówka do ust": ["konturówka do ust", "konturówki do ust"],
                            "balsam do ust": ["balsam do ust", "balsamy do ust"],
                            "lakier do paznokci": ["lakier do paznokci", "lakiery do paznokci"],
                            "odżywka do paznokci": ["odżywka do paznokci", "odżywki do paznokci"],
                            "zmywacz do paznokci": ["zmywacz do paznokci", "zmywacze do paznokci"],
                            "pędzel do makijażu": ["pędzel do makijażu", "pędzle do makijażu"],
                            "gąbeczka do makijażu": ["gąbeczka do makijażu", "gąbeczki do makijażu"],
                            "temperówka do ołówków": ["temperówka do ołówków", "temperówki do ołówków"],
                            "pilnik do paznokci": ["pilnik do paznokci", "pilniki do paznokci"],
                            "cążki do paznokci": ["cążki do paznokci"],
                            "pęseta": ["pęseta", "pęsety"],
                            "perfumy": ["perfum", "perfumy"],
                            "woda toaletowa": ["woda toaletowa", "wody toaletowe"],
                            "woda perfumowana": ["woda perfumowana", "wody perfumowane"],
                            "szampon": ["szampon", "szampony"],
                            "odżywka do włosów": ["odżywka do włosów", "odżywki do włosów"],
                            "maska do włosów": ["maska do włosów", "maski do włosów"],
                            "olejek do włosów": ["olejek do włosów", "olejki do włosów"],
                            "lakier do włosów": ["lakier do włosów", "lakiery do włosów"],
                            "pianka do włosów": ["pianka do włosów", "pianki do włosów"],
                            "demakijaż": ["demakijaż"],
                            "płatki kosmetyczne": ["płatek kosmetyczny", "płatki kosmetyczne"],
                            "patyczki kosmetyczne": ["patyczek kosmetyczny", "patyczki kosmetyczne"],
                            "gąbka do peelingu": ["gąbka do peelingu", "gąbki do peelingu"],
                            "rękawiczki kosmetyczne": ["rękawiczka kosmetyczna", "rękawiczki kosmetyczne"],
                            "makijaż permanentny": ["makijaż permanentny"],
                            "paleta do makijażu": ["paleta do makijażu", "palety do makijażu"]
}

                        detected_colors = [c for c in possible_colors if c in description.lower()]

                        detected_products = []
                        for singular, variants in product_singular_map.items():
                            for v in variants:
                                if v in description.lower():
                                    detected_products.append(singular)  # always singular
                                    break

                        st.session_state.photo_colors = detected_colors
                        st.session_state.photo_products = detected_products

                        # Assign unique ID to reset Tab 4
                        st.session_state.photo_id = str(time.time())

                        if not detected_colors:
                            st.warning("⚠️ Nie wykryto kolorów w opisie lub kolory nie są dozwolone.")
                        if not detected_products:
                            st.warning("⚠️ Nie wykryto typów produktów w opisie.")

                    except Exception as e:
                        st.error(f"❌ Błąd przy generowaniu opisu: {e}")
            else:
                st.error("❌ Nie załadowano obrazu lub brak klucza OpenAI.")

    # ---------------------------
    # Display description if exists
    # ---------------------------
    if st.session_state.get("photo_description"):
        st.markdown("### Opis zdjęcia:")
        st.markdown(st.session_state.photo_description)





# ============================================================
# TAB 4: Slogans Generator
# ============================================================

with tab4:
    st.markdown("### Generowanie sloganów reklamowych dla segmentów na podstawie kolorów i/lub typów produktów ze zdjęcia")
    # Read from session_state with fallback
    photo_colors = st.session_state.get("photo_colors", [])
    photo_products = st.session_state.get("photo_products", [])

    main_color = photo_colors[0] if photo_colors else None
    main_product = photo_products[0] if photo_products else None

    # ---------------------------
    # Reset slogans if photo changed (but not on first app run)
    # ---------------------------
    current_photo_id = st.session_state.get("photo_id")
    last_photo_id_for_slogans = st.session_state.get("last_photo_id_for_slogans")

    # Only reset if there was a previous photo
    if last_photo_id_for_slogans is not None and current_photo_id != last_photo_id_for_slogans:
        st.session_state.pop("slogans_data", None)
        st.info("🖼️ Zmieniono zdjęcie — poprzednie slogany zostały wyczyszczone.")

    # Always update the stored ID (for future comparisons)
    if current_photo_id:
        st.session_state["last_photo_id_for_slogans"] = current_photo_id
    # ---------------------------
    # Pull main color & product type from Tab3 (Opis zdjęcia)
    # ---------------------------
    photo_colors = st.session_state.get("photo_colors", [])
    photo_products = st.session_state.get("photo_products", [])

    main_color = photo_colors[0] if photo_colors else None
    main_product = photo_products[0] if photo_products else None

    # Display at the top
    if main_color:
        st.markdown(f"**Kolor:** {main_color}")
    else:
        st.info("Nie wykryto koloru. Czy opis zdjęcia został wygenerowany?")

    if main_product:
        st.markdown(f"**Typ produktu:** {main_product}")
    else:
        st.info("Nie wykryto typu produktu.Czy opis zdjęcia został wygenerowany?")

        # ---------------------------
    # Polish colors with gender/plural variants
    # ---------------------------
    colors_dict = {
        "gray": ["szary", "szara", "szare", "szarość"],
        "maroon": ["bordowy", "bordowa", "bordowe"],
        "turquoise": ["turkusowy", "turkusowa", "turkusowe"],
        "white": ["biały", "biała", "białe"],
        "charcoal": ["grafitowy", "grafitowa", "grafitowe"],
        "silver": ["srebrny", "srebrna", "srebrne", "srebro"],
        "pink": ["różowy", "różowa", "różowe", "róż"],
        "purple": ["fioletowy", "fioletowa", "fioletowe", "fiolet"],
        "violet": ["fioletowy", "fioletowa", "fioletowe"],
        "olive": ["oliwkowy", "oliwkowa", "oliwkowe"],
        "gold": ["złoty", "złota", "złote"],
        "teal": ["turkusowozielony", "turkusowozielona", "turkusowozielone", "morski"],
        "black": ["czarny", "czarna", "czarne", "czerń"],
        "green": ["zielony", "zielona", "zielone", "zieleń"],
        "peach": ["brzoskwiniowy", "brzoskwiniowa", "brzoskwiniowe"],
        "red": ["czerwony", "czerwona", "czerwone", "czerwień"],
        "cyan": ["cyjanowy", "cyjanowa", "cyjanowe"],
        "brown": ["brązowy", "brązowa", "brązowe"],
        "beige": ["beżowy", "beżowa", "beżowe"],
        "orange": ["pomarańczowy", "pomarańczowa", "pomarańczowe", "pomarańcz"],
        "indigo": ["granatowy", "granatowa", "granatowe"],
        "navy": ["granatowy", "granatowa", "granatowe"],
        "yellow": ["żółty", "żółta", "żółte", "żółć"],
        "magenta": ["fuksja", "magenta"],
        "blue": ["niebieski", "niebieska", "niebieskie"],
        "sky blue": ["błękitny", "błękitna", "błękitne"],
        "lavender": ["lawendowy", "lawendowa", "lawendowe"],
        "cream": ["kremowy", "kremowa", "kremowe", "ecru"],
        "ivory": ["ecru", "ivory"],
        "khaki": ["khaki", "oliwkowy jasny"],
        "camel": ["karmelowy", "camel"],
        "burgundy": ["burgundowy", "burgundowa", "burgundowe"],
        "mint": ["miętowy", "miętowa", "miętowe"],
        "denim": ["dżinsowy", "dżinsowa", "dżinsowe"],
        "multicolor": ["wielokolorowy", "wielokolorowa", "wielokolorowe"]
    }

    # ============================================================
    # PRODUCT DICTIONARY — ALL CATEGORIES
    # ============================================================
    product_dict = {
        "sukienka": ["sukienka", "sukienki", "dress", "dresses"],
        "spodnie": ["spodnie", "pants", "trousers", "jeans"],
        "spódnica": ["spódnica", "spódnice", "skirt", "skirts"],
        "bluzka": ["bluzka", "bluzki", "blouse", "blouses", "top", "tops"],
        "sweter": ["sweter", "swetry", "sweater", "pull", "pullover"],
        "t-shirt": ["t-shirt", "t-shirty", "koszulka", "tee", "tshirts"],
        "koszula": ["koszula", "koszule", "shirt", "shirts"],
        "kurtka": ["kurtka", "kurtki", "jacket", "jackets"],
        "płaszcz": ["płaszcz", "płaszcze", "coat", "coats"],
        "marynarka": ["marynarka", "marynarki", "blazer", "blazers"],
        "garnitur": ["garnitur", "garnitury", "suit", "suits"],
        "kamizelka": ["kamizelka", "kamizelki", "vest", "waistcoat"],
        "kombinezon": ["kombinezon", "kombinezony", "jumpsuit", "romper"],
        "legginsy": ["legginsy", "leggings"],
        "szorty": ["szorty", "shorts"],
        "buty": ["but", "buty", "shoes", "footwear"],
        "sandały": ["sandał", "sandały", "sandals"],
        "trampki": ["trampki", "sneakers", "trainers"],
        "kozaki": ["kozaki", "boots"],
        "botki": ["botki", "ankle boots"],
        "szpilki": ["szpilki", "heels", "pumps"],
        "mokasyny": ["mokasyny", "loafers"],
        "baletki": ["baletki", "flats", "ballet shoes"],
        "kapcie": ["kapcie", "slippers"],
        "okulary": ["okulary", "okulary przeciwsłoneczne", "glasses", "sunglasses"],
        "biżuteria": ["biżuteria", "jewelry"],
        "naszyjnik": ["naszyjnik", "naszyjniki", "necklace", "necklaces"],
        "bransoletka": ["bransoletka", "bransoletki", "bracelet", "bracelets"],
        "pierścionek": ["pierścionek", "pierścionki", "ring", "rings"],
        "kolczyki": ["kolczyki", "earrings"],
        "zegarek": ["zegarek", "zegarki", "watch", "watches"],
        "torebka": ["torebka", "torebki", "bag", "handbag", "purse"],
        "torebka": ["torebka", "torebki", "bag", "handbag", "purse"],
        "plecak": ["plecak", "plecaki", "backpack"],
        "portfel": ["portfel", "portfele", "wallet"],
        "pasek": ["pasek", "paski", "belt", "belts"],
        "szalik": ["szalik", "szaliki", "scarf", "scarves"],
        "apaszka": ["apaszka", "apaszki", "scarf", "neck scarf"],
        "czapka": ["czapka", "czapki", "hat", "cap"],
        "kapelusz": ["kapelusz", "kapelusze", "hat"],
        "rękawiczki": ["rękawiczki", "gloves"],
        "skarpetki": ["skarpetki", "socks"],
        "rajstopy": ["rajstopy", "tights"],
        "bielizna": ["bielizna", "underwear", "lingerie"],
        "biustonosz": ["biustonosz", "biustonosze", "bra", "bras"],
        "majtki": ["majtki", "panties", "briefs"],
        "piżama": ["piżama", "piżamy", "pajamas", "sleepwear"],
        "szlafrok": ["szlafrok", "szlafroki", "bathrobe", "robe"],
        "kostium kąpielowy": ["kostium kąpielowy", "stroje kąpielowe", "swimsuit", "bathing suit"],
        "bikini": ["bikini"],

        # ⚡ ELECTRONICS
        "smartfon": ["smartfon", "telefon", "phone", "smartphone", "mobile"],
        "laptop": ["laptop", "notebook", "komputer przenośny"],
        "komputer": ["komputer", "desktop", "pc"],
        "tablet": ["tablet", "ipad"],
        "monitor": ["monitor", "ekran", "display"],
        "telewizor": ["telewizor", "tv", "television"],
        "drukarka": ["drukarka", "printer"],
        "skaner": ["skaner", "scanner"],
        "aparat fotograficzny": ["aparat", "camera", "fotoaparat"],
        "obiektyw": ["obiektyw", "lens"],
        "głośnik": ["głośnik", "speaker", "soundbar"],
        "słuchawki": ["słuchawki", "headphones", "earphones", "earbuds"],
        "mysz": ["mysz", "mouse"],
        "klawiatura": ["klawiatura", "keyboard"],
        "router": ["router", "modem", "wi-fi router"],
        "konsola": ["konsola", "console", "playstation", "xbox", "nintendo"],
        "drukarka 3D": ["drukarka 3D", "3D printer"],
        "powerbank": ["powerbank", "bateria przenośna"],
        "ładowarka": ["ładowarka", "charger", "cable", "usb cable"],
        "odtwarzacz": ["odtwarzacz", "player", "mp3", "cd player"],
        "dron": ["dron", "drone"],
        "kamera": ["kamera", "video camera", "camcorder"],

        # 🏠 HOUSEWARE & HOME DECOR
        "mebel": ["mebel", "meble", "furniture"],
        "sofa": ["sofa", "kanapa", "couch"],
        "krzesło": ["krzesło", "krzesła", "chair", "chairs"],
        "stół": ["stół", "stoły", "table", "tables"],
        "biurko": ["biurko", "desk"],
        "szafa": ["szafa", "garderoba", "wardrobe", "closet"],
        "łóżko": ["łóżko", "bed"],
        "materac": ["materac", "mattress"],
        "dywan": ["dywan", "carpet", "rug"],
        "zasłona": ["zasłona", "zasłony", "curtain", "drapes"],
        "poduszka": ["poduszka", "poduszki", "pillow", "cushion"],
        "pościel": ["pościel", "bedding", "duvet", "sheets"],
        "lampka": ["lampka", "lampa", "lamp", "light"],
        "lustro": ["lustro", "mirror"],
        "obraz": ["obraz", "obrazy", "painting", "artwork", "poster"],
        "ramka": ["ramka", "ramki", "frame", "photo frame"],
        "świeca": ["świeca", "świece", "candle", "candles"],
        "dekoracja": ["dekoracja", "ozdoba", "decoration", "ornament"],
        "zegar": ["zegar", "clock", "wall clock"],
        "roślina": ["roślina", "kwiat", "plant", "flower", "succulent"],

        # 🍽️ KITCHENWARE & COOKWARE
        "garnek": ["garnek", "garnki", "pot", "saucepan", "casserole"],
        "patelnia": ["patelnia", "patelnie", "pan", "frying pan", "wok", "grill pan"],
        "brytfanna": ["brytfanna", "baking dish", "roasting pan"],
        "forma do pieczenia": ["forma do pieczenia", "baking form", "cake tin", "baking tray"],
        "noże kuchenne": ["nóż kuchenny", "noże kuchenne", "knife", "knives"],
        "łyżka": ["łyżka", "spoon", "chochla", "ladle"],
        "widelec": ["widelec", "fork"],
        "deska do krojenia": ["deska do krojenia", "cutting board"],
        "tarka": ["tarka", "grater", "peeler"],
        "czajnik": ["czajnik", "kettle", "electric kettle"],
        "mikser": ["mikser", "mixer", "blender", "food processor"],
        "piekarnik": ["piekarnik", "oven"],
        "mikrofalówka": ["mikrofalówka", "microwave"],
        "ekspres do kawy": ["ekspres do kawy", "coffee maker", "coffee machine"],
        "toster": ["toster", "toaster", "sandwich maker"],
        "zmywarka": ["zmywarka", "dishwasher"],
        "płyta indukcyjna": ["płyta indukcyjna", "hob", "stovetop"],
        "talerz": ["talerz", "plate", "dish"],
        "kubek": ["kubek", "mug", "cup"],
        "szklanka": ["szklanka", "glass"],
        "kieliszek": ["kieliszek", "wine glass", "goblet"],
        "dzbanek": ["dzbanek", "jug", "carafe", "pitcher"],
        "pojemnik": ["pojemnik", "container", "storage box"],
        "termos": ["termos", "thermos", "flask"],
        "chlebak": ["chlebak", "bread box"],
        "ręcznik kuchenny": ["ręcznik kuchenny", "kitchen towel"],
        "fartuch": ["fartuch", "apron"],
        "rękawica": ["rękawica kuchenna", "oven mitt"],
        "zlew": ["zlew", "sink"],
        "lodówka": ["lodówka", "refrigerator", "fridge"],
        "zmywak": ["zmywak", "gąbka", "sponge", "dish sponge"],

        # 💄 BEAUTY & COSMETICS
        # Skin products
        "podkład": ["podkład", "foundation"],
        "korektor": ["korektor", "concealer"],
        "puder": ["puder", "powder"],
        "róż": ["róż", "blush"],
        "bronzer": ["bronzer"],
        "rozświetlacz": ["rozświetlacz", "highlighter"],
        "baza pod makijaż": ["baza pod makijaż", "primer"],
        "utrwalacz makijażu": ["utrwalacz makijażu", "setting spray"],
        "maska do twarzy": ["maska do twarzy", "face mask"],
        "krem": ["krem", "cream", "moisturizer"],
        "serum": ["serum"],
        "tonik": ["tonik", "toner"],
        "peeling": ["peeling", "scrub", "exfoliator"],
            
        # Eye products
        "cienie do powiek": ["cienie do powiek", "eyeshadow", "eye shadow", "shadows"],
        "eyeliner": ["eyeliner", "kajal", "eye liner"],
        "maskara": ["maskara", "tusz do rzęs", "mascara"],
        "baza pod cienie": ["baza pod cienie", "eye shadow primer"],
        "żel do brwi": ["żel do brwi", "eyebrow gel"],
        "ołówek do brwi": ["ołówek do brwi", "eyebrow pencil"],
        "cienie do brwi": ["cienie do brwi", "eyebrow powder"],
            
        # Lip products
        "pomadka": ["pomadka", "lipstick", "lip color"],
        "błyszczyk": ["błyszczyk", "lip gloss"],
        "konturówka do ust": ["konturówka do ust", "lip liner"],
        "balsam do ust": ["balsam do ust", "lip balm"],
          
        # Nail products
        "lakier do paznokci": ["lakier do paznokci", "nail polish"],
        "odżywka do paznokci": ["odżywka do paznokci", "nail strengthener"],
        "zmywacz do paznokci": ["zmywacz do paznokci", "nail polish remover"],
           
        # Tools & brushes
        "pędzel do makijażu": ["pędzel do makijażu", "makeup brush", "brush"],
        "gąbeczka do makijażu": ["gąbeczka do makijażu", "makeup sponge", "beauty blender"],
        "temperówka do ołówków": ["temperówka do ołówków", "pencil sharpener"],
        "pilnik do paznokci": ["pilnik do paznokci", "nail file"],
        "cążki do paznokci": ["cążki do paznokci", "nail clippers"],
        "pęseta": ["pęseta", "tweezers"],
           
        # Fragrance
        "perfumy": ["perfumy", "perfume", "fragrance"],
        "woda toaletowa": ["woda toaletowa", "eau de toilette"],
        "woda perfumowana": ["woda perfumowana", "eau de parfum"],
            
        # Haircare
        "szampon": ["szampon", "shampoo"],
        "odżywka do włosów": ["odżywka do włosów", "conditioner"],
        "maska do włosów": ["maska do włosów", "hair mask"],
        "olejek do włosów": ["olejek do włosów", "hair oil"],
        "lakier do włosów": ["lakier do włosów", "hairspray"],
        "pianka do włosów": ["pianka do włosów", "hair mousse"],
            
        # Miscellaneous beauty
        "demakijaż": ["demakijaż", "makeup remover"],
        "płatki kosmetyczne": ["płatki kosmetyczne", "cotton pads"],
        "patyczki kosmetyczne": ["patyczki kosmetyczne", "cotton swabs", "q-tips"],
        "gąbka do peelingu": ["gąbka do peelingu", "exfoliating sponge"],
        "rękawiczki kosmetyczne": ["rękawiczki kosmetyczne", "cosmetic gloves"],
            
        # Permanent makeup
        "makijaż permanentny": ["makijaż permanentny", "permanent makeup"],
        "paleta do makijażu": ["paleta do makijażu", "makeup palette"]
}

       

    # ---------------------------
    # Ensure clusters exist
    # ---------------------------
    if st.session_state.get('df_clusters') is None or st.session_state.get('df_with_clusters') is None:
        st.warning("Brak danych o segmentach. Upewnij się, że Tab 2 został uruchomiony.")
    else:
        openai_client = st.session_state.get("openai_client", None)
        if openai_client is None:
            st.error("OpenAI client nie jest dostępny. Uruchom najpierw Tab 2.")
        else:
            # Initialize persistent storage for slogans
            if 'slogans_data' not in st.session_state:
                st.session_state.slogans_data = []

            # Working copy of clusters
            all_clusters = st.session_state.df_clusters.copy()

            # ✅ Standardize column names (fix KeyError)
            if 'Nazwa' not in all_clusters.columns and 'Name' in all_clusters.columns:
                all_clusters.rename(columns={'Name': 'Nazwa'}, inplace=True)

            if 'Opis' not in all_clusters.columns and 'Description' in all_clusters.columns:
                all_clusters.rename(columns={'Description': 'Opis'}, inplace=True)

            # Now safe to use
            all_clusters['description_lower'] = all_clusters['Opis'].astype(str).str.lower()

            # ---------------------------
            # Generate slogans button
            # ---------------------------
            if st.button("Generuj slogany dla pasujących segmentów"):
                placeholder_slogans = st.empty()
                placeholder_slogans.info("📝 Tworzenie sloganów...")

                if all_clusters.empty:
                    st.error("❌ Brak danych o segmentach. Uruchom ponownie Tab 1.")
                else:
                    progress_bar = st.progress(0)
                    total_rows = len(all_clusters)
                    generated_count = 0
                    slogans_dict = {}

                    for idx, row in all_clusters.iterrows():
                        desc_lower = row['description_lower']
                        matches_color = main_color.lower() in desc_lower if main_color else False

                        matches_product = False
                        if main_product:
                            variants = product_dict.get(main_product, [main_product])
                            for v in variants:
                                if v.lower() in desc_lower:
                                    matches_product = True
                                    break

                        if matches_color or matches_product:
                            cluster_name = f"Cluster {idx}: {row['Nazwa']}"
                            cluster_desc = row['Opis']
                            slogans_dict.setdefault(cluster_name, {"desc": cluster_desc, "slogans": []})

                            for i in range(5):
                                prompt = f"""
                                Stwórz chwytliwy slogan reklamowy dla grupy klientów opisanej jako:
                                {cluster_name}: {cluster_desc}

                                Kolor widoczny na zdjęciu: {main_color if main_color else 'brak'}.
                                Typ produktu widoczny na zdjęciu: {main_product if main_product else 'brak'}.

                                Slogan powinien być krótki, atrakcyjny marketingowo, lekko poetycki i zachęcający do zakupu produktu widocznego na zdjęciu.
                                Nie używaj wyrażeń sportowy, sportowa, sportowe.
                                """
                                try:
                                    response = openai_client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        temperature=0.7,
                                        messages=[{"role": "user", "content": prompt}]
                                    )
                                    slogan_text = response.choices[0].message.content.strip()
                                except Exception as e:
                                    slogan_text = f"❌ Błąd przy generowaniu sloganu: {e}"

                                slogans_dict[cluster_name]["slogans"].append(slogan_text)

                        generated_count += 1
                        progress_bar.progress(int((generated_count / total_rows) * 100))

                    placeholder_slogans.success("✅ Generowanie sloganów zakończone!")
                    st.session_state.slogans_data = slogans_dict

            # Build a mapping from cluster name to Segment number
            cluster_to_segment = {}
            if st.session_state.get('df_clusters') is not None:
                df = st.session_state.df_clusters
                for _, row in df.iterrows():
                    cluster_idx = int(row["Cluster"])
                    name = row.get("Name", "").strip()
                    segment_number = cluster_idx + 1  # Convert 0 → Segment 1, 1 → Segment 2...
                    cluster_to_segment[f"Cluster {cluster_idx}"] = {
                        "segment_number": segment_number,
                        "name": name
                    }


            # ---------------------------
            # Display grouped slogans (persistent)
            # ---------------------------
            if st.session_state.get("slogans_data"):
                st.markdown("## ✨ Wygenerowane slogany")
                for cluster_name, data in st.session_state.slogans_data.items():

                    cluster_key = cluster_name.split(":")[0]  # "Cluster 0"
                    cluster_info = cluster_to_segment.get(cluster_key)

                    if cluster_info:
                        segment_number = cluster_info["segment_number"]
                        segment_name = cluster_info["name"]
                        st.markdown(f"### 🧩 Segment {segment_number}: {segment_name}")
                    else:
                        st.markdown(f"### 🧩 {cluster_key}")  # fallback

                    st.markdown(f"**Opis:** {data['desc']}")

                    for i, slogan in enumerate(data["slogans"], 1):
                        st.markdown(f"- {slogan}")

                # ---------------------------
                # Download CSV (UTF-8 with BOM for Polish)
                # ---------------------------
                import pandas as pd
                import datetime

                csv_rows = []
                for cluster_name, data in st.session_state.slogans_data.items():
                    for slogan in data["slogans"]:
                        csv_rows.append({
                            "Nazwa klastra": cluster_name,
                            "Opis klastra": data["desc"],
                            "Slogan": slogan
                        })

                if csv_rows:
                    df_slogans = pd.DataFrame(csv_rows)
                    csv_data = df_slogans.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
                    st.download_button(
                        label="📥 Pobierz slogany jako CSV",
                        data=csv_data,
                        file_name=f"slogany_{timestamp}.csv",
                        mime="text/csv",
                        key="download_slogans"
                    )

                # ---------------------------
                # Clear button to reset slogans
                # ---------------------------
                if st.button("🗑️ Wyczyść slogany"):
                    st.session_state.pop("slogans_data", None)
                    # no rerun needed

# ============================================================
# TAB 5: Instructions
# ============================================================
with tab5:
    st.markdown("### Instrukcja obsługi aplikacji")

    st.markdown("""
1. **Pobierz plik wzorcowy** w formacie Excel z pierwszej zakładki: **"Plik źródłowy Excel"**.
2. **Uzupełnij plik danymi klientów** (nie usuwaj i nie zmieniaj nagłówków kolumn).
3. W drugiej zakładce **"Segmentacja danych"** załaduj uzupełniony plik.  
   Poczekaj, aż aplikacja:
   - wyświetli podgląd pierwszych pięciu wierszy,
   - zweryfikuje zgodność danych z szablonem.
4. Gdy pojawi się przycisk **"Oblicz optymalną liczbę segmentów"**, kliknij go.  
   Aplikacja wyznaczy najkorzystniejszą liczbę segmentów dla Twojego zbioru.
5. Kliknij **"Uruchom segmentację"**.  
   Dane zostaną podzielone na segmenty.  
   Pod tabelą pojawią się dwa przyciski:
   - **Pobierz pełny plik z segmentami (CSV)**
   - **Generuj nazwy i opisy segmentów**
6. Kliknij **"Generuj nazwy i opisy segmentów"** i poczekaj na wygenerowanie tabeli.
7. Pod tabelą z nazwami i opisami segmentów pojawi się przycisk umożliwiający **zapisanie wygenerowanego pliku**.
8. W trzeciej zakładce **"Produkt dla grup docelowych"** załaduj zdjęcie produktu pasujące do przynajmniej jednego segmentu (kolor, typ produktu).
9. Kliknij przycisk **"Generuj opis zdjęcia"** znajdujący się pod załadowanym zdjęciem.
10. W czwartej zakładce **"Slogany reklamowe"** kliknij **"Generuj slogany dla pasujących segmentów"**.
    """)
