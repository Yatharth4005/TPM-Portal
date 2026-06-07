import json
import datetime
from django.shortcuts import render
from django.db.models import Avg, Sum
from tpm.models import Department, PillarEntry, KPIValue, WorkstationValue, WorkstationKPI
from tpm.utils.decorators import admin_required
from tpm.utils.calculations import compute_achievement

def sidebar_context_processor(request):
    if not request.user.is_authenticated:
        return {}
    
    if request.user.is_admin():
        depts = Department.objects.all().order_by('name')
    else:
        depts = Department.objects.filter(id=request.user.department_id).order_by('name')
        
    pillars = [
        {'id': 'KK', 'label': 'KK (Kobetsu Kaizen)'},
        {'id': 'JH', 'label': 'JH (Jishu Hozen)'},
        {'id': 'PM', 'label': 'PM (Planned Maintenance)'},
        {'id': 'QM', 'label': 'QM (Quality Maintenance)'},
        {'id': 'ET', 'label': 'ET (Education & Training)'},
        {'id': 'DM', 'label': 'DM (Initial Flow/Design)'},
        {'id': 'SHE', 'label': 'SHE (Safety & Health)'},
        {'id': 'OTPM', 'label': 'OTPM (Office TPM)'},
    ]
    return {
        'sidebar_departments': depts,
        'pillars': pillars,
    }


@admin_required
def plant_dashboard(request):
    today = datetime.date.today()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    depts = Department.objects.all().order_by('name')
    
    # 1. Plant Overall OEE (average KK row 1 actuals for selected month/year)
    oee_avg = KPIValue.objects.filter(
        pillar_entry__pillar='KK',
        pillar_entry__month=selected_month,
        pillar_entry__year=selected_year,
        sl_no='1'
    ).aggregate(avg=Avg('actual'))['avg'] or 0.0

    # 2. Total YTD Kaizens (KK sl_no='7' actuals YTD)
    kaizen_ytd = KPIValue.objects.filter(
        pillar_entry__pillar='KK',
        pillar_entry__year=selected_year,
        pillar_entry__month__lte=selected_month,
        sl_no='7'
    ).aggregate(total=Sum('actual'))['total'] or 0.0

    # 3. SHE: Zero LTI Count (sum of LTI numbers for the selected month/year)
    lti_sum = KPIValue.objects.filter(
        pillar_entry__pillar='SHE',
        pillar_entry__month=selected_month,
        pillar_entry__year=selected_year,
        sl_no__in=['2A', '2B']  # Fatal + LTI
    ).aggregate(total=Sum('actual'))['total'] or 0.0

    # 4. PM Compliance (average of PM scheduled compliance row 14)
    pm_compliance = KPIValue.objects.filter(
        pillar_entry__pillar='PM',
        pillar_entry__month=selected_month,
        pillar_entry__year=selected_year,
        sl_no='14'
    ).aggregate(avg=Avg('actual'))['avg'] or 0.0

    # Department Cards Detail YTD
    dept_cards = []
    for d in depts:
        # Compute department average achievement across all pillars for the month
        # Standard 8 pillars:
        kpi_vals = KPIValue.objects.filter(
            pillar_entry__department=d,
            pillar_entry__month=selected_month,
            pillar_entry__year=selected_year
        )
        
        achievements = []
        for val in kpi_vals:
            if val.actual is not None and val.target is not None:
                ach = compute_achievement(val.actual, val.target, val.kpi_name)
                achievements.append(ach)
                
        # Workstation KPIs
        ws_vals = WorkstationValue.objects.filter(
            workstation_kpi__workstation__department=d,
            month=selected_month,
            year=selected_year
        )
        for val in ws_vals:
            if val.actual is not None and val.workstation_kpi.commitment is not None:
                indicator = val.workstation_kpi.goodness_indicator
                target = val.workstation_kpi.commitment
                if indicator == 'LOWER':
                    ach = min(100.0, (target / val.actual) * 100.0) if val.actual != 0 else 100.0
                else:
                    ach = (val.actual / target) * 100.0 if target != 0 else 100.0
                achievements.append(ach)

        avg_achievement = sum(achievements) / len(achievements) if achievements else 0.0
        
        # Color Class mapping
        if avg_achievement >= 90.0:
            status = 'on-track'
            status_class = 'bg-success-subtle text-success border-success'
        elif avg_achievement >= 75.0:
            status = 'at-risk'
            status_class = 'bg-warning-subtle text-warning border-warning'
        else:
            status = 'behind'
            status_class = 'bg-danger-subtle text-danger border-danger'
            
        # Sparkline data (OEE actuals over last 6 months)
        sparkline_data = []
        for m in range(max(1, selected_month - 5), selected_month + 1):
            val = KPIValue.objects.filter(
                pillar_entry__department=d,
                pillar_entry__pillar='KK',
                pillar_entry__month=m,
                pillar_entry__year=selected_year,
                sl_no='1'
            ).first()
            sparkline_data.append(val.actual if val else 0.0)

        dept_cards.append({
            'id': d.id,
            'name': d.name,
            'code': d.code,
            'achievement': round(avg_achievement, 1),
            'status': status,
            'status_class': status_class,
            'sparkline': sparkline_data,
        })

    # Top & Bottom Performers
    sorted_cards = sorted(dept_cards, key=lambda x: x['achievement'], reverse=True)
    top_performers = sorted_cards[:5]
    bottom_performers = sorted_cards[-5:][::-1] if len(sorted_cards) >= 5 else sorted_cards[::-1]

    # Chart data structure: Monthly Plant OEE trend (Line chart, Jan-Dec)
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    oee_trend_actuals = []
    oee_trend_targets = []
    
    for m in range(1, 13):
        avg_act = KPIValue.objects.filter(
            pillar_entry__pillar='KK',
            pillar_entry__month=m,
            pillar_entry__year=selected_year,
            sl_no='1'
        ).aggregate(avg=Avg('actual'))['avg'] or None
        oee_trend_actuals.append(avg_act)
        oee_trend_targets.append(85.0)  # Plant benchmark target is 85%

    # Radar Chart: average achievement for each of the 9 pillars plant-wide
    radar_data = []
    radar_labels = ['KK', 'JH', 'PM', 'QM', 'ET', 'DM', 'SHE', 'OTPM', 'WS KPI']
    for pillar in ['KK', 'JH', 'PM', 'QM', 'ET', 'DM', 'SHE', 'OTPM']:
        vals = KPIValue.objects.filter(
            pillar_entry__pillar=pillar,
            pillar_entry__month=selected_month,
            pillar_entry__year=selected_year
        )
        ach_list = []
        for val in vals:
            if val.actual is not None and val.target is not None:
                ach_list.append(compute_achievement(val.actual, val.target, val.kpi_name))
        radar_data.append(round(sum(ach_list)/len(ach_list), 1) if ach_list else 0.0)

    # Workstation KPI average achievement
    ws_kpis = WorkstationValue.objects.filter(month=selected_month, year=selected_year)
    ws_ach_list = []
    for val in ws_kpis:
        if val.actual is not None and val.workstation_kpi.commitment is not None:
            indicator = val.workstation_kpi.goodness_indicator
            target = val.workstation_kpi.commitment
            if indicator == 'LOWER':
                ach = min(100.0, (target / val.actual) * 100.0) if val.actual != 0 else 100.0
            else:
                ach = (val.actual / target) * 100.0 if target != 0 else 100.0
            ws_ach_list.append(ach)
    radar_data.append(round(sum(ws_ach_list)/len(ws_ach_list), 1) if ws_ach_list else 0.0)

    # Compliance Heatmap Grid (28 departments x last 6 months)
    heatmap = []
    heatmap_months = []
    for i in range(5, -1, -1):
        target_month = selected_month - i
        target_year = selected_year
        if target_month <= 0:
            target_month += 12
            target_year -= 1
        heatmap_months.append({
            'month': target_month,
            'year': target_year,
            'label': f"{months_labels[target_month-1]} '{str(target_year)[-2:]}"
        })

    for d in depts:
        row = {'dept_name': d.name, 'scores': []}
        for hm in heatmap_months:
            # calculate average achievement
            kpis = KPIValue.objects.filter(
                pillar_entry__department=d,
                pillar_entry__month=hm['month'],
                pillar_entry__year=hm['year']
            )
            ach_list = []
            for k in kpis:
                if k.actual is not None and k.target is not None:
                    ach_list.append(compute_achievement(k.actual, k.target, k.kpi_name))
            
            ws_vals = WorkstationValue.objects.filter(
                workstation_kpi__workstation__department=d,
                month=hm['month'],
                year=hm['year']
            )
            for ws_v in ws_vals:
                if ws_v.actual is not None and ws_v.workstation_kpi.commitment is not None:
                    indicator = ws_v.workstation_kpi.goodness_indicator
                    target = ws_v.workstation_kpi.commitment
                    if indicator == 'LOWER':
                        ach = min(100.0, (target / ws_v.actual) * 100.0) if ws_v.actual != 0 else 100.0
                    else:
                        ach = (ws_v.actual / target) * 100.0 if target != 0 else 100.0
                    ach_list.append(ach)

            avg_ach = sum(ach_list) / len(ach_list) if ach_list else None
            
            # color mapping
            color_class = 'bg-light text-muted'
            if avg_ach is not None:
                if avg_ach >= 90.0:
                    color_class = 'bg-success text-white'
                elif avg_ach >= 75.0:
                    color_class = 'bg-warning text-dark'
                else:
                    color_class = 'bg-danger text-white'

            row['scores'].append({
                'value': round(avg_ach, 1) if avg_ach is not None else 'N/A',
                'class': color_class
            })
        heatmap.append(row)

    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'oee_avg': round(oee_avg, 1),
        'kaizen_ytd': int(kaizen_ytd),
        'lti_sum': int(lti_sum),
        'pm_compliance': round(pm_compliance, 1),
        'dept_cards': dept_cards,
        'top_performers': top_performers,
        'bottom_performers': bottom_performers,
        'heatmap_months': heatmap_months,
        'heatmap': heatmap,
        'oee_trend_actuals_json': json.dumps(oee_trend_actuals),
        'oee_trend_targets_json': json.dumps(oee_trend_targets),
        'radar_labels_json': json.dumps(radar_labels),
        'radar_data_json': json.dumps(radar_data),
        'months_labels_json': json.dumps(months_labels),
    }
    return render(request, 'dashboard/plant_dashboard.html', context)
