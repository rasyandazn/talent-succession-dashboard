import dash
from dash import dcc, html, dash_table, Input, Output, callback_context
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as components # Pastikan sudah install dash-bootstrap-components
import dash
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import create_engine

# ==========================================
# 1. INITIALIZE DASH & SERVER
# ==========================================
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
server = app.server

# CONNECTION STRING TO NEON CLOUD DATABASE
DATABASE_URL = "postgresql://neondb_owner:npg_ZL6MTFNnx4SH@ep-jolly-union-aojg4zdh.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

try:
    print("Attempting to connect to Neon Cloud Database...")
    engine = create_engine(DATABASE_URL)
    
    # Baca langsung dari tabel SQL di Neon
    df_master = pd.read_sql_query("SELECT * FROM talent_master", engine)
    df_mobility = pd.read_sql_query("SELECT * FROM talent_mobility", engine)

    # Re-create 'Grade_Num' column based on 'Job_Level_Grade'
    if 'Job_Level_Grade' in df_master.columns:
        df_master['Grade_Num'] = pd.to_numeric(df_master['Job_Level_Grade'], errors='coerce')
    else:
        df_master['Grade_Num'] = 3.0  # Nilai default cadangan
    
    print("🚀 Connection successful!")

# If connection fails, fallback to reading local CSV files
except Exception as e:
    print(f"❌ Failed to connect to Neon because: {e}")
    # Emergency fallback: read from local CSV files
    df_master = pd.read_csv('df_master.csv', encoding='utf-8')
    df_mobility = pd.read_csv('df_mobility.csv', encoding='utf-8')
    
# ==========================================
# 2. BACKEND ENGINE FUNCTIONS 
# ==========================================

# Function to get upcoming vacancies based on department and risk horizon
def get_upcoming_vacancies(target_dept, target_horizon):
    vacant_pool = df_master[
        (df_master['Department'] == target_dept) & 
        (df_master['Retirement_Horizon'] == target_horizon)
    ]
    return vacant_pool[['Employee_ID', 'Full_Name', 'Current_Position', 'Department', 'Job_Level_Grade', 'Assigned_Unit_Type', 'Territory_Region', 'Age']]

# Function to find potential successors based on department, grade level, and region
def find_potential_successors(target_dept, target_grade_level, target_region):
    target_grade = float(target_grade_level)
    past_experienced_id = df_mobility[df_mobility['Past_Department'] == target_dept]['Employee_ID'].unique()

    base_pool = df_master[
        (df_master['Grade_Num'] > target_grade) &
        (df_master['Grade_Num'] <= target_grade + 1.5) &
        (df_master['Retirement_Horizon'] == 'Stable')
    ].copy()

    filtered_successors = []

    for idx, row in base_pool.iterrows():
        is_same_dept = row['Department'] == target_dept
        is_same_region = row['Territory_Region'] == target_region
        has_past_experience = row['Employee_ID'] in past_experienced_id
        mobility = row['Mobility_Transferability']
        grade_distance = row['Grade_Num'] - target_grade

        if (not is_same_region) and (mobility == 'Local-Only'):
            continue 
        
        if is_same_dept and is_same_region and (grade_distance <= 1.0):
            tier = "🥇 Tier 1: Local Perfect Match (Ready Now - Same Dept & Region)"
        elif is_same_dept and (not is_same_region) and (mobility in ['National-Wide', 'Territory-Wide']) and (grade_distance <= 1.0):
            tier = "🥇 Tier 1B: Regional Import (Ready Now - Same Dept, Cross-Region Approved)"
        elif has_past_experience:
            tier = "🥈 Tier 2: Functional Reserve (Cross Functional Talent)"
        elif is_same_dept and (grade_distance > 1.0):
            tier = "🥉 Tier 3A: Internal Development (Same Dept but Needs Training)"
        else:
            tier = "🏅 Tier 3B: Structural Ready (Close Grade, Cross-Functional but Needs Exposure)"
        
        filtered_successors.append({
            'Employee_ID': row['Employee_ID'],
            'Full_Name': row['Full_Name'],
            'Current_Position': row['Current_Position'],
            'Department': row['Department'],
            'Job_Level_Grade': row['Job_Level_Grade'],
            'Assigned_Unit_Type': row['Assigned_Unit_Type'],
            'Territory_Region': row['Territory_Region'],
            'Age': row['Age'],
            'Mobility_Transferability': row['Mobility_Transferability'],
            'Successor_Fit_Tier': tier
        })
  
    df_result = pd.DataFrame(filtered_successors)
    if df_result.empty:
        return pd.DataFrame()

    tier_order = [
        "🥇 Tier 1: Local Perfect Match (Ready Now - Same Dept & Region)",
        "🥇 Tier 1B: Regional Import (Ready Now - Same Dept, Cross-Region Approved)",
        "🥈 Tier 2: Functional Reserve (Cross Functional Talent)",
        "🥉 Tier 3A: Internal Development (Same Dept but Needs Training)",
        "🏅 Tier 3B: Structural Ready (Close Grade, Cross-Functional but Needs Exposure)"
    ]
    df_result['Successor_Fit_Tier'] = pd.Categorical(df_result['Successor_Fit_Tier'], categories=tier_order, ordered=True)
    return df_result.sort_values(by=['Successor_Fit_Tier', 'Age'], ascending=[True, False])

# ==========================================
# 3. FRONTEND LAYOUT DESIGN
# ==========================================
app.layout = components.Container([
    
    # HEADER TITLE
    html.Div([
        html.H1("Executive Talent Succession & Analytics Dashboard", style={'textAlign': 'left', 'fontWeight': 'bold', 'color': '#2C3E50'}),
        html.P("Real-time workforce risk mitigation and pipeline matching system.", style={'textAlign': 'left', 'color': '#7F8C8D'}),
        html.Hr()
    ], style={'marginTop': '20px'}),

    # ----------------------------------------------------------------------
    # STEP 1: GLOBAL SUMMARY METRICS & MINI BREAKDOWN CHARTS (Macro View)
    # ----------------------------------------------------------------------
    components.Row([
        # KPI Cards Column
        components.Col([
            html.Div([
                html.H5("🔴 Critical Vacancies (<12 Mo)", style={'color': '#C0392B'}),
                html.H2(id='kpi-critical', style={'fontWeight': 'bold', 'color': '#C0392B'})
            ], className='card shadow-sm p-3 mb-3 bg-white rounded', style={'borderLeft': '5px solid #C0392B'}),
            
            html.Div([
                html.H5("🟡 Urgent Vacancies (1-3 Yrs)", style={'color': '#D35400'}),
                html.H2(id='kpi-urgent', style={'fontWeight': 'bold', 'color': '#D35400'})
            ], className='card shadow-sm p-3 mb-3 bg-white rounded', style={'borderLeft': '5px solid #D35400'}),
            
            html.Div([
                html.H5("🟢 Watchlist Positions (3-5 Yrs)", style={'color': '#27AE60'}),
                html.H2(id='kpi-watchlist', style={'fontWeight': 'bold', 'color': '#27AE60'})
            ], className='card shadow-sm p-3 bg-white rounded', style={'borderLeft': '5px solid #27AE60'}),
        ], width=4),
        
        # Mini Breakdown Chart Column
        components.Col([
            html.Div([
                dcc.Graph(id='mini-dept-chart', config={'displayModeBar': False})
            ], className='card shadow-sm p-2 bg-white rounded')
        ], width=4),
        
        components.Col([
            html.Div([
                dcc.Graph(id='mini-region-chart', config={'displayModeBar': False})
            ], className='card shadow-sm p-2 bg-white rounded')
        ], width=4)
    ], className='mb-4'),

    html.Hr(),

    # ----------------------------------------------------------------------
    # STEP 2 & 3: DRILL-DOWN FILTER & ACTIONABLE TABLES (Micro View)
    # ----------------------------------------------------------------------
    components.Row([
        html.H3("🔎 Interactive Talent Deep-Dive", style={'fontWeight': 'bold', 'color': '#2C3E50', 'marginBottom': '15px'})
    ]),

    # Interactive Dropdown Filters
    components.Row([
        components.Col([
            html.Label("Select Department:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='dept-dropdown',
                options=[{'label': dept, 'value': dept} for dept in df_master['Department'].unique()] if not df_master.empty else [],
                placeholder="Choose Department...",
                clearable=False
            )
        ], width=6),
        components.Col([
            html.Label("Select Risk Horizon:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='horizon-dropdown',
                options=[
                    {'label': '🔴 Critical Risk (<12 Months)', 'value': '🔴 Critical (<12 Mo)'},
                    {'label': '🟡 Urgent Risk (1-3 Years)', 'value': '🟡 Urgent (1-3 Yrs)'},
                    {'label': '🟢 Watchlist Risk (3-5 Years)', 'value': '🟢 Watchlist (3-5 Yrs)'}
                ],
                value='🔴 Critical (<12 Mo)',
                clearable=False
            )
        ], width=6)
    ], className='mb-4'),

    # Table 1: Vacant Positions (The Trigger Table)
    components.Row([
        components.Col([
            html.Div([
                html.H5("⚠️ Risk Positions Identified (Click a row to find successors)", style={'fontWeight': 'bold', 'color': '#34495E'}),
               dash_table.DataTable(
                    id='vacancy-table',
                    # Dynamically generate columns based on df_master structure, but only show relevant ones
                    columns=[{"name": i.replace('_', ' '), "id": i} for i in df_master.columns if i in ['Employee_ID', 'Full_Name', 'Current_Position', 'Job_Level_Grade', 'Territory_Region', 'Age']],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '10px'},
                    style_header={'backgroundColor': '#2C3E50', 'color': 'white', 'fontWeight': 'bold'},
                    row_selectable=False,
                    cell_selectable=True,
                    style_as_list_view=True
                )
            ], className='card shadow-sm p-3 bg-white rounded')
        ], width=12)
    ], className='mb-4'),

    # Table 2 & Tier Distribution Chart: Successor Recommendation
    components.Row([
        # Successor Table Column
        components.Col([
            html.Div([
                html.H5("🎯 Real-time Successor Pipeline Matrix", style={'fontWeight': 'bold', 'color': '#27AE60'}),
                html.P(id='selected-position-text', style={'fontStyle': 'italic', 'color': '#7F8C8D'}),
                
                # Dropdown Filter for Successor Tier
                html.Div([
                    html.Label("Filter by Readiness:", style={'fontWeight': 'bold', 'fontSize': '12px'}),
                    dcc.Dropdown(
                        id='tier-filter-dropdown',
                        options=[{'label': 'All Tiers', 'value': 'ALL'}],
                        value='ALL',
                        clearable=False,
                        style={'width': '250px', 'marginBottom': '10px'}
                    )
                ]),

                dash_table.DataTable(
                    id='successor-table',
                    columns=[{"name": i.replace('_', ' '), "id": i} for i in ['Full_Name', 'Current_Position', 'Department', 'Job_Level_Grade', 'Territory_Region', 'Successor_Fit_Tier']],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '10px'},
                    style_header={'backgroundColor': '#27AE60', 'color': 'white', 'fontWeight': 'bold'},
                    style_as_list_view=True
                )
            ], className='card shadow-sm p-3 bg-white rounded')
        ], width=8),

        # Mini Distribution Successor Chart
        components.Col([
            html.Div([
                dcc.Graph(id='successor-tier-chart', config={'displayModeBar': False})
            ], className='card shadow-sm p-2 bg-white rounded')
        ], width=4)
    ], className='mb-5')

], fluid=True)


# ==========================================
# 4. REACTIVE CALLBACK LOGIC
# ==========================================

# CALLBACK 1: KPI & MINI CHARTS ON INITIAL LOAD
@app.callback(
    [Output('kpi-critical', 'children'),
     Output('kpi-urgent', 'children'),
     Output('kpi-watchlist', 'children'),
     Output('mini-dept-chart', 'figure'),
     Output('mini-region-chart', 'figure')],
    [Input('vacancy-table', 'data')] # Dicuatkan saat data dimuat
)
def update_macro_analytics(_):
    if df_master.empty:
        return "0", "0", "0", {}, {}
        
    # Count the number of vacancies in each risk category
    crit_count = len(df_master[df_master['Retirement_Horizon'].str.contains('Critical', na=False)])
    urg_count = len(df_master[df_master['Retirement_Horizon'].str.contains('Urgent', na=False)])
    watch_count = len(df_master[df_master['Retirement_Horizon'].str.contains('Watchlist', na=False)])
    
    # Filter the DataFrame to only include critical risk positions for the mini charts
    red_zone_df = df_master[df_master['Retirement_Horizon'].str.contains('Critical', na=False)]
    
    # Generate mini bar charts for department and region distributions
    dept_counts = red_zone_df['Department'].value_counts().reset_index()
    fig_dept = px.bar(dept_counts, x='count', y='Department', orientation='h', 
                      title="🔴 Critical Risk by Dept", color_discrete_sequence=['#C0392B'])
    fig_dept.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=250, showlegend=False, yaxis={'categoryorder':'total ascending'})
    
    region_counts = red_zone_df['Territory_Region'].value_counts().reset_index()
    fig_region = px.bar(region_counts, x='count', y='Territory_Region', orientation='h', 
                        title="🔴 Critical Risk by Territory", color_discrete_sequence=['#E67E22'], text='Territory_Region')
    fig_region.update_layout(margin=dict(l=20, r=10, t=30, b=10), height=250, showlegend=False, yaxis={'categoryorder':'total ascending', 'visible': False})
    fig_region.update_traces(textposition='inside', textfont=dict(color='white', weight='bold'))

    return str(crit_count), str(urg_count), str(watch_count), fig_dept, fig_region

# CALLBACK 2: FILTER VACANCY TABLE BASED ON DROPDOWN
@app.callback(
    Output('vacancy-table', 'data'),
    [Input('dept-dropdown', 'value'),
     Input('horizon-dropdown', 'value')]
)
def update_vacancy_list(selected_dept, selected_horizon):
    if df_master.empty or not selected_dept:
        return []
    vacant_df = get_upcoming_vacancies(selected_dept, selected_horizon)
    return vacant_df.to_dict('records')


# CALLBACK 3: TRIGGER SUCCESSOR AUTO-MATCH BASED ON TABLE CLICK 
@app.callback(
    [Output('successor-table', 'data'),
     Output('selected-position-text', 'children'),
     Output('successor-tier-chart', 'figure'),
     Output('tier-filter-dropdown', 'options')],
    [Input('vacancy-table', 'active_cell'),
     Input('vacancy-table', 'data'),
     Input('tier-filter-dropdown', 'value')]
)
def find_successors_from_click(active_cell, table_data, selected_tier_filter):
    # Jika tabel belum diklik, langsung return template kosong
    if not active_cell or not table_data:
        return [], "💡 Click anywhere on a row in the table above to trigger real-time successor analysis.", {}, [{'label': 'All Tiers', 'value': 'ALL'}]
    
    try:
        # 1. Take the clicked row's data to extract parameters
        row_index = active_cell['row']
        clicked_row_data = table_data[row_index]
        
        target_dept = clicked_row_data['Department']
        target_grade_level = clicked_row_data['Job_Level_Grade']
        target_region = clicked_row_data['Territory_Region']
        pos_name = clicked_row_data['Current_Position']
        holder_name = clicked_row_data['Full_Name']
        
        # Debugging logs to trace the callback execution
        print(f"\n[TRIGGER] User clicked on position: {pos_name}")
        print(f"[DEBUG] Extract parameters -> Dept: {target_dept} | Grade: {target_grade_level} | Region: {target_region}")

        # 2. Convert grade level to float for comparison, handle potential errors gracefully
        try:
            # If the grade level is a string, attempt to clean and convert it to float
            if isinstance(target_grade_level, str):
                # Take only digits and decimal points to avoid conversion errors (example: "Grade 3.5" -> "3.5")
                cleaned_grade = ''.join(c for c in target_grade_level if c.isdigit() or c == '.')
                target_grade = float(cleaned_grade)
            else:
                target_grade = float(target_grade_level)
        except Exception as e:
            print(f"[ERROR] Failed to convert grade '{target_grade_level}' to float: {e}")
            return [], f"❌ Error: Cannot process grade format '{target_grade_level}'. Please check your data data type.", {}, [{'label': 'All Tiers', 'value': 'ALL'}]

        # 3. Filter potential successors based on the extracted parameters
        # Bypass the mobility filter for candidates who have past experience in the target department
        past_experienced_id = df_mobility[df_mobility['Past_Department'] == target_dept]['Employee_ID'].unique()

        # Ensure 'Grade_Num' is numeric for comparison
        df_master['Grade_Num'] = pd.to_numeric(df_master['Grade_Num'], errors='coerce')

        base_pool = df_master[
            (df_master['Grade_Num'] > target_grade) &
            (df_master['Grade_Num'] <= target_grade + 1.5) &
            (df_master['Retirement_Horizon'].str.contains('Stable', na=False))
        ].copy()

        print(f"[DEBUG] Base pool available candidates count: {len(base_pool)}")

        filtered_successors = []
        for idx, row in base_pool.iterrows():
            is_same_dept = row['Department'] == target_dept
            is_same_region = row['Territory_Region'] == target_region
            has_past_experience = row['Employee_ID'] in past_experienced_id
            mobility = row['Mobility_Transferability']
            grade_distance = row['Grade_Num'] - target_grade

            if (not is_same_region) and (mobility == 'Local-Only'):
                continue 
            
            if is_same_dept and is_same_region and (grade_distance <= 1.0):
                tier = "🥇 Tier 1: Local Perfect Match (Ready Now - Same Dept & Region)"
            elif is_same_dept and (not is_same_region) and (mobility in ['National-Wide', 'Territory-Wide']) and (grade_distance <= 1.0):
                tier = "🥇 Tier 1B: Regional Import (Ready Now - Same Dept, Cross-Region Approved)"
            elif has_past_experience:
                tier = "🥈 Tier 2: Functional Reserve (Cross Functional Talent)"
            elif is_same_dept and (grade_distance > 1.0):
                tier = "🥉 Tier 3A: Internal Development (Same Dept but Needs Training)"
            else:
                tier = "🏅 Tier 3B: Structural Ready (Close Grade, Cross-Functional but Needs Exposure)"
            
            filtered_successors.append({
                'Full_Name': row['Full_Name'],
                'Current_Position': row['Current_Position'],
                'Department': row['Department'],
                'Job_Level_Grade': row['Job_Level_Grade'],
                'Territory_Region': row['Territory_Region'],
                'Successor_Fit_Tier': tier
            })
      
        successor_df = pd.DataFrame(filtered_successors)
        
        if successor_df.empty:
            print("[RESULT] Search completed. 0 successors found matching criteria.")
            info_text = f"⚠️ No active pipeline found for {pos_name} (Current Holder: {holder_name})"
            return [], info_text, {}, [{'label': 'All Tiers', 'value': 'ALL'}]
        
        print(f"[RESULT] Success! Found {len(successor_df)} potential successors.")

        # 4. Define dropdown options for tier filtering
        dropdown_options = [
            {'label': 'All Tiers', 'value': 'ALL'},
            {'label': '🥇 Tier 1: Local Perfect Match', 'value': '🥇 Tier 1: Local Perfect Match (Ready Now - Same Dept & Region)'},
            {'label': '🥇 Tier 1B: Regional Import', 'value': '🥇 Tier 1B: Regional Import (Ready Now - Same Dept, Cross-Region Approved)'},
            {'label': '🥈 Tier 2: Functional Reserve', 'value': '🥈 Tier 2: Functional Reserve (Cross Functional Talent)'},
            {'label': '🥉 Tier 3A: Internal Development', 'value': '🥉 Tier 3A: Internal Development (Same Dept but Needs Training)'},
            {'label': '🏅 Tier 3B: Structural Ready', 'value': '🏅 Tier 3B: Structural Ready (Close Grade, Cross-Functional but Needs Exposure)'}
        ]

        # 5. Generate tier distribution chart for the successors
        tier_counts = successor_df['Successor_Fit_Tier'].value_counts().reset_index()
        fig_tier = px.bar(tier_counts, x='count', y='Successor_Fit_Tier', orientation='h',
                          title="Pipeline Distribution", color='Successor_Fit_Tier',
                          color_discrete_sequence=px.colors.qualitative.Safe)
        
        tier_order_list = [
            "🏅 Tier 3B: Structural Ready (Close Grade, Cross-Functional but Needs Exposure)",
            "🥉 Tier 3A: Internal Development (Same Dept but Needs Training)",
            "🥈 Tier 2: Functional Reserve (Cross Functional Talent)",
            "🥇 Tier 1B: Regional Import (Ready Now - Same Dept, Cross-Region Approved)",
            "🥇 Tier 1: Local Perfect Match (Ready Now - Same Dept & Region)"
        ]
        
        fig_tier.update_layout(
            showlegend=False, 
            yaxis={
                'categoryorder': 'array', 
                'categoryarray': tier_order_list, # Kunci urutan bar chart
                'visible': False
            }, 
            height=220, 
            margin=dict(l=10, r=10, t=40, b=10)
        )

        # 6. Apply tier filter if selected
        if selected_tier_filter != 'ALL':
            successor_df = successor_df[successor_df['Successor_Fit_Tier'] == selected_tier_filter]

        info_text = f"📊 Analyzing Pipeline for: {pos_name} | Grade: {target_grade_level} | Location: {target_region} (Current Holder: {holder_name})"
        
        return successor_df.to_dict('records'), info_text, fig_tier, dropdown_options

    except Exception as global_error:
        # If any unexpected error occurs, log it and return a user-friendly message
        print(f"[FATAL CRASH] Callback 3 failed completely: {global_error}")
        return [], f"❌ System Error: {str(global_error)}", {}, [{'label': 'All Tiers', 'value': 'ALL'}]
    
if __name__ == '__main__':
    app.run(debug=True)