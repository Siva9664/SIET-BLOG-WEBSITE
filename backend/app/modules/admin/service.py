from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AnalyticsResponse,
    DashboardActivity,
    DashboardResponse,
    DashboardTotals,
    TodayAccuracy,
)


class AdminService:
    def __init__(self, repository: AdminRepository):
        self.repository = repository

    async def get_dashboard(self) -> DashboardResponse:
        totals_dict = await self.repository.get_dashboard_totals()
        totals = DashboardTotals(**totals_dict)
        
        today_acc_dict = await self.repository.get_today_accuracy()
        today_accuracy = TodayAccuracy(**today_acc_dict)

        activity_list = await self.repository.get_recent_activity()
        activities = [DashboardActivity(**act) for act in activity_list]
        
        return DashboardResponse(
            totals=totals,
            todayAccuracy=today_accuracy,
            recentActivity=activities,
        )

    async def get_analytics(self) -> AnalyticsResponse:
        analytics_dict = await self.repository.get_analytics()
        return AnalyticsResponse(**analytics_dict)
