import { Component, OnInit } from '@angular/core';
import { DashboardService } from './dashboard.service';

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  totalUsers: number = 0;
  totalOrders: number = 0;
  totalRevenue: number = 0;

  constructor(private dashboardService: DashboardService) { }

  ngOnInit(): void {
    this.loadDashboardData();
  }

  loadDashboardData(): void {
    this.dashboardService.getUserStats().subscribe(stats => {
      this.totalUsers = stats.users;
      this.totalOrders = stats.orders;
      this.totalRevenue = stats.revenue;
    });
  }

  goToUsers(): void {
    // TODO: Implement navigation to users page
    console.log('Navigating to users page...');
  }

  goToOrders(): void {
    // TODO: Implement navigation to orders page
    console.log('Navigating to orders page...');
  }
}
