import json
import datetime
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.contrib import messages
from tpm.models import Department, PillarEntry, KPIValue, WorkstationValue, Workstation
from tpm.utils.decorators import dept_access_required
from tpm.utils.calculations import compute_achievement

@dept_access_required
def dept_overview(request, dept_id):
    dept = get_object_or_404(Department, id=dept_id)
    today = datetime.date.today()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    pillars_meta = [
        {'id': 'KK', 'label': 'KK (Kobetsu Kaizen)', 'icon': '🎯'},
        {'id': 'JH', 'label': 'JH (Jishu Hozen)', 'icon': '⚙️'},
        {'id': 'PM', 'label': 'PM (Planned Maintenance)', 'icon': '🔧'},
        {'id': 'QM', 'label': 'QM (Quality Maintenance)', 'icon': '💎'},
        {'id': 'ET', 'label': 'ET (Education & Training)', 'icon': '📚'},
        {'id': 'DM', 'label': 'DM (Initial Flow/Design)', 'icon': '📐'},
        {'id': 'SHE', 'label': 'SHE (Safety & Environment)', 'icon': '🛡️'},
        {'id': 'OTPM', 'label': 'OTPM (Office TPM)', 'icon': '🏢'},
    ]
    
    pillar_cards = []
    
    # Standard 8 Pillars scores calculation
    for pm in pillars_meta:
        # Check if submitted
        entry = PillarEntry.objects.filter(
            department=dept,
            pillar=pm['id'],
            month=selected_month,
            year=selected_year
        ).first()
        
        status_label = 'Pending'
        status_class = 'badge-red'
        if entry:
            status_label = 'Locked' if entry.is_locked() else 'Draft'
            status_class = 'badge-green' if entry.is_locked() else 'badge-amber'
            
        kpis = KPIValue.objects.filter(pillar_entry=entry) if entry else []
        ach_list = []
        for k in kpis:
            if k.actual is not None and k.target is not None:
                ach_list.append(compute_achievement(k.actual, k.target, k.kpi_name))
        
        avg_ach = sum(ach_list) / len(ach_list) if ach_list else 0.0
        
        pillar_cards.append({
            'id': pm['id'],
            'label': pm['label'],
            'icon': pm['icon'],
            'achievement': round(avg_ach, 1),
            'status': status_label,
            'status_class': status_class,
        })
        
    # Workstation KPI (9th card)
    ws_vals = WorkstationValue.objects.filter(
        workstation_kpi__workstation__department=dept,
        month=selected_month,
        year=selected_year
    )
    ws_ach_list = []
    for val in ws_vals:
        if val.actual is not None and val.workstation_kpi.commitment is not None:
            indicator = val.workstation_kpi.goodness_indicator
            target = val.workstation_kpi.commitment
            if indicator == 'LOWER':
                ach = min(100.0, (target / val.actual) * 100.0) if val.actual != 0 else 100.0
            else:
                ach = (val.actual / target) * 100.0 if target != 0 else 100.0
            ws_ach_list.append(ach)
            
    ws_avg_ach = sum(ws_ach_list) / len(ws_ach_list) if ws_ach_list else 0.0
    has_workstations = Workstation.objects.filter(department=dept).exists()
    ws_status = 'N/A' if not has_workstations else ('Locked' if ws_vals.exists() else 'Pending')
    ws_class = 'badge-muted' if ws_status == 'N/A' else ('badge-green' if ws_status == 'Locked' else 'badge-red')
    
    pillar_cards.append({
        'id': 'ws-kpi',
        'label': 'Workstation KPI',
        'icon': '🏭',
        'achievement': round(ws_avg_ach, 1),
        'status': ws_status,
        'status_class': ws_class,
    })

    # OEE monthly actual vs target line chart trend (last 12 months)
    oee_trend_actuals = []
    oee_trend_targets = []
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for m in range(1, 13):
        val = KPIValue.objects.filter(
            pillar_entry__department=dept,
            pillar_entry__pillar='KK',
            pillar_entry__month=m,
            pillar_entry__year=selected_year,
            sl_no='1'
        ).first()
        oee_trend_actuals.append(val.actual if val else None)
        oee_trend_targets.append(val.target if val and val.target else 90.0)

    # 9-axis radar data for this department specifically
    radar_labels = ['KK', 'JH', 'PM', 'QM', 'ET', 'DM', 'SHE', 'OTPM', 'WS KPI']
    radar_data = [card['achievement'] for card in pillar_cards]

    # Recent submissions table (last 6 months submission status for all 8 pillars)
    recent_months = []
    for i in range(5, -1, -1):
        target_month = selected_month - i
        target_year = selected_year
        if target_month <= 0:
            target_month += 12
            target_year -= 1
        recent_months.append({
            'month': target_month,
            'year': target_year,
            'label': f"{months_labels[target_month-1]} '{str(target_year)[-2:]}"
        })

    submission_rows = []
    for pm in pillars_meta:
        row = {'pillar_label': pm['label'], 'pillar_id': pm['id'], 'months': []}
        for rm in recent_months:
            entry = PillarEntry.objects.filter(
                department=dept,
                pillar=pm['id'],
                month=rm['month'],
                year=rm['year']
            ).first()
            status_text = 'Pending'
            status_cls = 'text-danger'
            if entry:
                status_text = 'Locked' if entry.is_locked() else 'Draft'
                status_cls = 'text-success font-semibold' if entry.is_locked() else 'text-warning'
            row['months'].append({'status': status_text, 'class': status_cls})
        submission_rows.append(row)

    # Workstation KPI row for recent months table
    ws_row = {'pillar_label': 'Workstation KPI', 'pillar_id': 'ws-kpi', 'months': []}
    for rm in recent_months:
        vals = WorkstationValue.objects.filter(
            workstation_kpi__workstation__department=dept,
            month=rm['month'],
            year=rm['year']
        )
        status_text = 'Locked' if vals.exists() else 'Pending'
        status_cls = 'text-success font-semibold' if vals.exists() else 'text-danger'
        ws_row['months'].append({'status': status_text, 'class': status_cls})
    submission_rows.append(ws_row)

    context = {
        'dept': dept,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'pillar_cards': pillar_cards,
        'recent_months': recent_months,
        'submission_rows': submission_rows,
        'oee_trend_actuals_json': json.dumps(oee_trend_actuals),
        'oee_trend_targets_json': json.dumps(oee_trend_targets),
        'radar_labels_json': json.dumps(radar_labels),
        'radar_data_json': json.dumps(radar_data),
        'months_labels_json': json.dumps(months_labels),
    }
    return render(request, 'department/overview.html', context)
