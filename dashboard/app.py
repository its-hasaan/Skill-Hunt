"""
Skill Hunt Dashboard
====================
Interactive dashboard showing tech job market skill demand analysis.
Built with Streamlit + Plotly, data from Supabase.

Run locally: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Skill Hunt - Tech Job Market Analysis",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        background-color: #f0f2f6;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)


# Database connection
@st.cache_resource
def get_db_connection():
    """Create database connection using Streamlit secrets or env vars."""
    try:
        # Try Streamlit secrets first (for cloud deployment)
        if hasattr(st, 'secrets') and 'database' in st.secrets:
            return psycopg2.connect(
                host=st.secrets.database.host,
                port=int(st.secrets.database.port),  # Convert to int
                user=st.secrets.database.user,
                password=st.secrets.database.password,
                dbname=st.secrets.database.dbname,
                sslmode='require',
                connect_timeout=10
            )
        else:
            # Fall back to environment variable
            db_url = os.getenv("SUPABASE_URL")
            if not db_url:
                st.error("❌ No database credentials found. Please configure secrets.")
                return None
            return psycopg2.connect(db_url, sslmode='require')
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.info("💡 Check your secrets in Streamlit Cloud: Settings → Secrets")
        return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_skill_demand():
    """Load skill demand data from marts."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
        SELECT 
            skill_name, skill_category, search_role, country_code,
            job_count, demand_percentage, avg_salary_min, avg_salary_max,
            avg_salary_midpoint, rank_in_role_country, rank_in_role_global
        FROM staging_marts.mart_skill_demand
        WHERE rank_in_role_country <= 30
        ORDER BY search_role, country_code, rank_in_role_country
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_skill_cooccurrence():
    """Load skill co-occurrence data."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
        SELECT 
            skill_name_1, skill_category_1, skill_name_2, skill_category_2,
            search_role, cooccurrence_count, jaccard_similarity,
            prob_skill2_given_skill1, prob_skill1_given_skill2
        FROM staging_marts.mart_skill_cooccurrence
        WHERE cooccurrence_count >= 5
        ORDER BY search_role, cooccurrence_count DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_company_leaderboard():
    """Load company leaderboard data."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
        SELECT 
            company_name, search_role, country_code, job_count,
            avg_salary_min, avg_salary_max, avg_salary_midpoint,
            full_time_count, part_time_count, contract_count,
            rank_in_role_country
        FROM staging_marts.mart_company_leaderboard
        WHERE rank_in_role_country <= 50
        ORDER BY search_role, country_code, rank_in_role_country
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_role_similarity():
    """Load role similarity data."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
        SELECT 
            role_1, role_2, shared_skills_count,
            role_1_unique_skills, role_2_unique_skills,
            jaccard_similarity, overlap_coefficient, dice_coefficient,
            top_shared_skills
        FROM staging_marts.mart_role_similarity
        ORDER BY jaccard_similarity DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_salary_by_skill():
    """Load salary by skill data."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
        SELECT 
            skill_name, skill_category, search_role, country_code,
            salary_currency, jobs_with_skill,
            avg_salary_with_skill, median_salary_with_skill,
            market_avg_salary, salary_premium_absolute, salary_premium_percentage,
            rank_by_salary
        FROM staging_marts.mart_salary_by_skill
        WHERE jobs_with_skill >= 5
        ORDER BY search_role, country_code, salary_premium_percentage DESC NULLS LAST
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_skills_by_country():
    """Load skills by country data."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
        SELECT 
            skill_name, skill_category, search_role, country_code,
            job_count, demand_percentage, rank_by_country,
            top_country_for_skill, top_country_demand_pct
        FROM staging_marts.mart_skills_by_country
        WHERE job_count >= 3
        ORDER BY skill_name, search_role, demand_percentage DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def get_summary_stats():
    """Get high-level summary statistics."""
    conn = get_db_connection()
    if not conn:
        return {}
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Total jobs
    cursor.execute("SELECT COUNT(*) as count FROM staging.stg_jobs")
    total_jobs = cursor.fetchone()['count']
    
    # Total skills tracked
    cursor.execute("SELECT COUNT(DISTINCT skill_id) as count FROM staging.stg_job_skills")
    total_skills = cursor.fetchone()['count']
    
    # Countries
    cursor.execute("SELECT COUNT(DISTINCT country_code) as count FROM staging.stg_jobs")
    total_countries = cursor.fetchone()['count']
    
    # Roles
    cursor.execute("SELECT COUNT(DISTINCT search_role) as count FROM staging.stg_jobs")
    total_roles = cursor.fetchone()['count']
    
    # Companies
    cursor.execute("SELECT COUNT(DISTINCT company_name) as count FROM staging.stg_jobs WHERE company_name IS NOT NULL")
    total_companies = cursor.fetchone()['count']
    
    conn.close()
    
    return {
        'total_jobs': total_jobs,
        'total_skills': total_skills,
        'total_countries': total_countries,
        'total_roles': total_roles,
        'total_companies': total_companies
    }


# Country code to name mapping
COUNTRY_NAMES = {
    'gb': '🇬🇧 United Kingdom', 'us': '🇺🇸 United States', 'au': '🇦🇺 Australia',
    'at': '🇦🇹 Austria', 'be': '🇧🇪 Belgium', 'br': '🇧🇷 Brazil',
    'ca': '🇨🇦 Canada', 'de': '🇩🇪 Germany', 'fr': '🇫🇷 France',
    'in': '🇮🇳 India', 'it': '🇮🇹 Italy', 'mx': '🇲🇽 Mexico',
    'nl': '🇳🇱 Netherlands', 'nz': '🇳🇿 New Zealand', 'pl': '🇵🇱 Poland',
    'sg': '🇸🇬 Singapore', 'za': '🇿🇦 South Africa'
}


def get_country_name(code):
    """Convert country code to display name."""
    return COUNTRY_NAMES.get(code, code.upper() if code else 'Global')


# ============================================
# MAIN APP
# ============================================

def main():
    # Header
    st.markdown('<h1 class="main-header">🎯 Skill Hunt</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Tech Job Market Analysis Dashboard | Real-time Skill Demand Insights</p>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading data..."):
        skill_demand_df = load_skill_demand()
        cooccurrence_df = load_skill_cooccurrence()
        company_df = load_company_leaderboard()
        role_sim_df = load_role_similarity()
        salary_df = load_salary_by_skill()
        country_skills_df = load_skills_by_country()
        stats = get_summary_stats()
    
    if skill_demand_df.empty:
        st.error("⚠️ Could not load data. Please check database connection.")
        st.stop()
    
    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📋 Total Jobs", f"{stats.get('total_jobs', 0):,}")
    with col2:
        st.metric("🛠️ Skills Tracked", f"{stats.get('total_skills', 0):,}")
    with col3:
        st.metric("🌍 Countries", f"{stats.get('total_countries', 0):,}")
    with col4:
        st.metric("💼 Roles", f"{stats.get('total_roles', 0):,}")
    with col5:
        st.metric("🏢 Companies", f"{stats.get('total_companies', 0):,}")
    
    st.divider()
    
    # Sidebar filters
    st.sidebar.header("🔍 Filters")
    
    # Role filter
    roles = sorted(skill_demand_df['search_role'].unique())
    selected_role = st.sidebar.selectbox("Select Role", roles, index=0)
    
    # Country filter
    countries = sorted(skill_demand_df['country_code'].dropna().unique())
    country_options = ['All Countries'] + [get_country_name(c) for c in countries]
    selected_country_display = st.sidebar.selectbox("Select Country", country_options, index=0)
    
    # Convert display name back to code
    if selected_country_display == 'All Countries':
        selected_country = None
    else:
        selected_country = [k for k, v in COUNTRY_NAMES.items() if v == selected_country_display][0]
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Top Skills", 
        "🔗 Skill Connections", 
        "💰 Salary Analysis",
        "🏢 Top Companies",
        "🌍 Global Comparison",
        "🔄 Career Paths"
    ])
    
    # ============================================
    # TAB 1: Top Skills
    # ============================================
    with tab1:
        st.header(f"Top Skills for {selected_role}")
        
        # Filter data
        filtered_df = skill_demand_df[skill_demand_df['search_role'] == selected_role]
        if selected_country:
            filtered_df = filtered_df[filtered_df['country_code'] == selected_country]
            title_suffix = f" in {get_country_name(selected_country)}"
        else:
            # Aggregate across countries
            filtered_df = filtered_df.groupby(['skill_name', 'skill_category']).agg({
                'job_count': 'sum',
                'avg_salary_midpoint': 'mean'
            }).reset_index()
            filtered_df = filtered_df.sort_values('job_count', ascending=False).head(20)
            title_suffix = " (Global)"
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Bar chart of top skills
            top_skills = filtered_df.nlargest(15, 'job_count')
            
            fig = px.bar(
                top_skills,
                x='job_count',
                y='skill_name',
                orientation='h',
                color='skill_category',
                title=f"Top 15 Skills{title_suffix}",
                labels={'job_count': 'Number of Jobs', 'skill_name': 'Skill', 'skill_category': 'Category'},
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Skill category breakdown
            category_counts = filtered_df.groupby('skill_category')['job_count'].sum().reset_index()
            
            fig2 = px.pie(
                category_counts,
                values='job_count',
                names='skill_category',
                title="Skills by Category",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig2.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig2, use_container_width=True)
        
        # Skills table
        st.subheader("📋 Full Skills Breakdown")
        display_df = filtered_df[['skill_name', 'skill_category', 'job_count']].copy()
        display_df.columns = ['Skill', 'Category', 'Job Count']
        st.dataframe(display_df.head(30), use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 2: Skill Co-occurrence
    # ============================================
    with tab2:
        st.header(f"Skill Connections for {selected_role}")
        st.markdown("*Skills that frequently appear together in job postings*")
        
        # Filter co-occurrence data
        cooc_filtered = cooccurrence_df[cooccurrence_df['search_role'] == selected_role]
        
        if cooc_filtered.empty:
            st.warning("No co-occurrence data available for this role.")
        else:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Select a skill to see its connections
                skills_in_cooc = sorted(set(cooc_filtered['skill_name_1'].tolist() + cooc_filtered['skill_name_2'].tolist()))
                selected_skill = st.selectbox("Select a skill to see its connections:", skills_in_cooc[:50])
                
                # Get connections for selected skill
                skill_connections = cooc_filtered[
                    (cooc_filtered['skill_name_1'] == selected_skill) | 
                    (cooc_filtered['skill_name_2'] == selected_skill)
                ].head(15)
                
                # Create connection data
                connections = []
                for _, row in skill_connections.iterrows():
                    other_skill = row['skill_name_2'] if row['skill_name_1'] == selected_skill else row['skill_name_1']
                    connections.append({
                        'Connected Skill': other_skill,
                        'Co-occurrence': row['cooccurrence_count'],
                        'Similarity': f"{row['jaccard_similarity']:.2%}"
                    })
                
                if connections:
                    st.subheader(f"Skills that pair with {selected_skill}")
                    st.dataframe(pd.DataFrame(connections), use_container_width=True, hide_index=True)
            
            with col2:
                # Network visualization (simplified as bubble chart)
                top_pairs = cooc_filtered.nlargest(20, 'cooccurrence_count')
                
                fig = px.scatter(
                    top_pairs,
                    x='skill_name_1',
                    y='skill_name_2',
                    size='cooccurrence_count',
                    color='jaccard_similarity',
                    title="Top Skill Pairs",
                    labels={'cooccurrence_count': 'Co-occurrence', 'jaccard_similarity': 'Similarity'},
                    color_continuous_scale='Viridis'
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
    
    # ============================================
    # TAB 3: Salary Analysis
    # ============================================
    with tab3:
        st.header(f"Salary Analysis for {selected_role}")
        
        # Filter salary data
        salary_filtered = salary_df[salary_df['search_role'] == selected_role]
        if selected_country:
            salary_filtered = salary_filtered[salary_filtered['country_code'] == selected_country]
        
        if salary_filtered.empty:
            st.warning("No salary data available for this selection.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("💎 Skills with Highest Salary Premium")
                
                # Top premium skills
                top_premium = salary_filtered.nlargest(15, 'salary_premium_percentage')
                
                fig = px.bar(
                    top_premium,
                    x='salary_premium_percentage',
                    y='skill_name',
                    orientation='h',
                    title="Salary Premium by Skill (%)",
                    labels={'salary_premium_percentage': 'Premium %', 'skill_name': 'Skill'},
                    color='salary_premium_percentage',
                    color_continuous_scale='RdYlGn'
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("📈 Average Salary by Skill")
                
                # Top paying skills
                top_paying = salary_filtered.nlargest(15, 'avg_salary_with_skill')
                
                fig = px.bar(
                    top_paying,
                    x='avg_salary_with_skill',
                    y='skill_name',
                    orientation='h',
                    title="Average Salary by Skill",
                    labels={'avg_salary_with_skill': 'Average Salary', 'skill_name': 'Skill'},
                    color='skill_category',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500)
                st.plotly_chart(fig, use_container_width=True)
            
            # Salary comparison table
            st.subheader("📊 Skill Salary Comparison")
            salary_table = salary_filtered[['skill_name', 'skill_category', 'jobs_with_skill', 
                                           'avg_salary_with_skill', 'market_avg_salary', 
                                           'salary_premium_percentage']].copy()
            salary_table.columns = ['Skill', 'Category', 'Jobs', 'Avg Salary', 'Market Avg', 'Premium %']
            salary_table['Avg Salary'] = salary_table['Avg Salary'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
            salary_table['Market Avg'] = salary_table['Market Avg'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
            salary_table['Premium %'] = salary_table['Premium %'].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else 'N/A')
            st.dataframe(salary_table.head(20), use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 4: Company Leaderboard
    # ============================================
    with tab4:
        st.header(f"Top Hiring Companies for {selected_role}")
        
        # Filter company data
        company_filtered = company_df[company_df['search_role'] == selected_role]
        if selected_country:
            company_filtered = company_filtered[company_filtered['country_code'] == selected_country]
        
        if company_filtered.empty:
            st.warning("No company data available for this selection.")
        else:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Top companies bar chart
                top_companies = company_filtered.nlargest(20, 'job_count')
                
                fig = px.bar(
                    top_companies,
                    x='job_count',
                    y='company_name',
                    orientation='h',
                    title=f"Top 20 Hiring Companies",
                    labels={'job_count': 'Job Postings', 'company_name': 'Company'},
                    color='job_count',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=600, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Contract type breakdown
                st.subheader("Contract Types")
                contract_data = pd.DataFrame({
                    'Type': ['Full Time', 'Part Time', 'Contract'],
                    'Count': [
                        company_filtered['full_time_count'].sum(),
                        company_filtered['part_time_count'].sum(),
                        company_filtered['contract_count'].sum()
                    ]
                })
                contract_data = contract_data[contract_data['Count'] > 0]
                
                fig = px.pie(
                    contract_data,
                    values='Count',
                    names='Type',
                    title="Job Types Distribution",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Company table
            st.subheader("📋 Company Details")
            company_table = company_filtered[['company_name', 'job_count', 'full_time_count', 
                                              'avg_salary_midpoint', 'rank_in_role_country']].copy()
            company_table.columns = ['Company', 'Total Jobs', 'Full-Time', 'Avg Salary', 'Rank']
            company_table['Avg Salary'] = company_table['Avg Salary'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else 'N/A')
            st.dataframe(company_table.head(30), use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 5: Global Comparison
    # ============================================
    with tab5:
        st.header("Global Skill Demand Comparison")
        
        # Select skill for comparison
        available_skills = sorted(country_skills_df['skill_name'].unique())
        selected_skill_compare = st.selectbox("Select a skill to compare across countries:", available_skills[:100])
        
        # Filter for selected skill and role
        compare_df = country_skills_df[
            (country_skills_df['skill_name'] == selected_skill_compare) &
            (country_skills_df['search_role'] == selected_role)
        ]
        
        if compare_df.empty:
            st.warning("No data available for this skill/role combination.")
        else:
            compare_df['country_name'] = compare_df['country_code'].apply(get_country_name)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Demand percentage by country
                fig = px.bar(
                    compare_df.sort_values('demand_percentage', ascending=True),
                    x='demand_percentage',
                    y='country_name',
                    orientation='h',
                    title=f"Demand for {selected_skill_compare} by Country",
                    labels={'demand_percentage': 'Demand %', 'country_name': 'Country'},
                    color='demand_percentage',
                    color_continuous_scale='Viridis'
                )
                fig.update_layout(height=500, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Job count by country
                fig = px.bar(
                    compare_df.sort_values('job_count', ascending=True),
                    x='job_count',
                    y='country_name',
                    orientation='h',
                    title=f"Job Count with {selected_skill_compare}",
                    labels={'job_count': 'Jobs', 'country_name': 'Country'},
                    color='job_count',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=500, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            
            # Comparison table
            st.subheader("📊 Country Comparison Table")
            compare_table = compare_df[['country_name', 'job_count', 'demand_percentage', 'total_jobs']].copy()
            compare_table.columns = ['Country', 'Jobs with Skill', 'Demand %', 'Total Jobs']
            compare_table['Demand %'] = compare_table['Demand %'].apply(lambda x: f"{x:.1f}%")
            st.dataframe(compare_table.sort_values('Jobs with Skill', ascending=False), 
                        use_container_width=True, hide_index=True)
    
    # ============================================
    # TAB 6: Career Paths (Role Similarity)
    # ============================================
    with tab6:
        st.header("🔄 Career Transition Guide")
        st.markdown("*Discover how similar different tech roles are based on required skills*")
        
        if role_sim_df.empty:
            st.warning("No role similarity data available.")
        else:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Role similarity heatmap
                # Prepare matrix data
                all_roles = sorted(set(role_sim_df['role_1'].tolist() + role_sim_df['role_2'].tolist()))
                
                # Create similarity matrix
                sim_matrix = pd.DataFrame(index=all_roles, columns=all_roles, dtype=float)
                sim_matrix = sim_matrix.fillna(0)
                
                # Fill diagonal with 1s
                for role in all_roles:
                    sim_matrix.loc[role, role] = 1.0
                
                # Fill from data
                for _, row in role_sim_df.iterrows():
                    sim_matrix.loc[row['role_1'], row['role_2']] = row['jaccard_similarity']
                    sim_matrix.loc[row['role_2'], row['role_1']] = row['jaccard_similarity']
                
                fig = px.imshow(
                    sim_matrix.values,
                    x=all_roles,
                    y=all_roles,
                    color_continuous_scale='RdYlGn',
                    title="Role Similarity Heatmap",
                    labels={'color': 'Similarity'}
                )
                fig.update_layout(height=600)
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Select current role to see transitions
                st.subheader("🎯 Find Your Path")
                current_role = st.selectbox("I am currently a:", all_roles)
                
                # Find similar roles
                similar_roles = role_sim_df[
                    (role_sim_df['role_1'] == current_role) | 
                    (role_sim_df['role_2'] == current_role)
                ].copy()
                
                # Get the other role and format
                similar_roles['target_role'] = similar_roles.apply(
                    lambda x: x['role_2'] if x['role_1'] == current_role else x['role_1'], axis=1
                )
                similar_roles = similar_roles.sort_values('jaccard_similarity', ascending=False)
                
                st.markdown(f"**Roles similar to {current_role}:**")
                
                for _, row in similar_roles.iterrows():
                    similarity = row['jaccard_similarity']
                    target = row['target_role']
                    shared = row['shared_skills_count']
                    
                    # Color based on similarity
                    if similarity >= 0.5:
                        color = "🟢"
                        difficulty = "Easy transition"
                    elif similarity >= 0.3:
                        color = "🟡"
                        difficulty = "Moderate transition"
                    else:
                        color = "🔴"
                        difficulty = "Significant upskilling needed"
                    
                    st.markdown(f"""
                    {color} **{target}**  
                    Similarity: {similarity:.0%} | Shared skills: {shared} | {difficulty}
                    """)
                
                # Show shared skills for selected transition
                st.subheader("📚 Shared Skills")
                target_role = st.selectbox("Compare with:", similar_roles['target_role'].tolist())
                
                row = similar_roles[similar_roles['target_role'] == target_role].iloc[0]
                if row['top_shared_skills']:
                    shared_skills = row['top_shared_skills']
                    if isinstance(shared_skills, str):
                        shared_skills = shared_skills.strip('{}').split(',')
                    st.write("Skills you already have:")
                    for skill in shared_skills[:10]:
                        st.markdown(f"✅ {skill.strip()}")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #888; font-size: 0.9rem;'>
        <p>🎯 Skill Hunt | Data refreshed weekly from Adzuna API</p>
        <p>Built with Streamlit • Data Engineering Portfolio Project</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
