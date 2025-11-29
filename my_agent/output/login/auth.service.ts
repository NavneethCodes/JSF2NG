import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = '/api/auth'; // Replace with your actual API endpoint

  constructor(private http: HttpClient) { }

  login(username: string, password: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/login`, { username, password })
      .pipe(
        catchError(error => {
          console.error('Authentication error', error);
          // You might want to parse the error response for more specific messages
          let errorMessage = 'An unknown error occurred.';
          if (error.error instanceof ErrorEvent) {
            // Client-side or network error
            errorMessage = `Client-side error: ${error.error.message}`;
          } else if (error.status === 401) {
            // Unauthorized error
            errorMessage = 'Invalid username or password.';
          } else if (error.error && typeof error.error.message === 'string') {
            // Server-side error message
            errorMessage = error.error.message;
          }
          // Throw an observable error
          return throwError(() => new Error(errorMessage || 'Login failed. Please try again.'));
        })
      );
  }
}
