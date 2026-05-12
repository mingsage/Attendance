from io import BytesIO

from openpyxl import Workbook


def build_attendance_workbook(records) -> BytesIO:
    """把考勤记录导出为 Excel 二进制流。"""

    wb = Workbook()
    ws = wb.active
    ws.title = "考勤记录"
    ws.append(["时间", "课程", "学号", "姓名", "班级", "状态", "置信度", "活体分", "情绪", "备注"])
    for item in records:
        student = item.student
        ws.append(
            [
                item.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                item.course_name,
                student.student_no if student else "",
                student.name if student else "",
                student.class_name if student else "",
                item.status,
                item.confidence,
                item.liveness_score,
                item.emotion_type or "",
                item.message or "",
            ]
        )
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def build_attendance_stats_workbook(students: list[dict], dates: list[str]) -> BytesIO:
    """把课程考勤统计导出为 Excel。

    students: [{name, class_name, checkin: {date: bool}}, ...]
    dates:    ["2026-05-11", "2026-05-12", ...]
    """

    wb = Workbook()
    ws = wb.active
    ws.title = "考勤统计"

    # 汇总
    total = len(students)
    signed_total = sum(1 for s in students if any(s.get("checkin", {}).get(d) for d in dates))
    rate = f"{signed_total / total * 100:.1f}%" if total else "0%"
    ws.append(["到课率", rate, f"应到 {total} 人", f"实到 {signed_total} 人", f"缺勤 {total - signed_total} 人"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2)
    if len(dates) == 1:
        absent_names = [s["name"] for s in students if not s.get("checkin", {}).get(dates[0])]
        if absent_names:
            ws.append(["未签到", "、".join(absent_names)])
    ws.append([])  # 空行分隔

    # 表头
    row_idx = ws.max_row + 1
    headers = ["姓名", "班级"]
    for d in dates:
        headers.append(d)
    headers.append("总签到次数")
    ws.append(headers)

    for student in students:
        row = [student["name"], student.get("class_name", "")]
        total = 0
        for d in dates:
            checked = student.get("checkin", {}).get(d, False)
            row.append("✓" if checked else "")
            if checked:
                total += 1
        row.append(total)
        ws.append(row)

    # 冻结表头行
    ws.freeze_panes = f"A{row_idx + 1}"
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
