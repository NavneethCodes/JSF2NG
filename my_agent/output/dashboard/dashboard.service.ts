import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class DashboardService {
  private apiUrl = '/api/dashboard'; // Replace with your actual API endpoint

  constructor(private http: HttpClient) { }

  getUserStats(): Observable<{ users: number, orders: number, revenue: number }> {
    return this.http.get<{ users: number, orders: number, revenue: number }>(`${this.apiUrl}/user-stats`)
      .pipe(
        catchError(error => {
          console.error('Error fetching user stats', error);
          return of({ users: 0, orders: 0, revenue: 0 }); // Return empty data on error
        })
      );
  }
}
