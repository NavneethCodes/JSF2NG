import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

// Define User and UserRole interfaces
export enum UserRole {
  USER = 'USER',
  ADMIN = 'ADMIN'
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private apiUrl = '/api/users'; // Base API URL for users

  constructor(private http: HttpClient) { }

  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(this.apiUrl).pipe(
      catchError(error => {
        console.error('Error fetching users:', error);
        return of([]); // Return empty array on error
      })
    );
  }

  searchUsers(keyword: string): Observable<User[]> {
    if (!keyword) {
      return this.getUsers(); // If keyword is empty, return all users
    }
    let params = new HttpParams();
    params = params.append('keyword', keyword);

    return this.http.get<User[]>(`${this.apiUrl}/search`, { params }).pipe(
      catchError(error => {
        console.error('Error searching users:', error);
        return of([]);
      })
    );
  }

  getUserById(id: string): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/${id}`).pipe(
      catchError(error => {
        console.error(`Error fetching user with ID ${id}:`, error);
        // Throw error to be handled by the component
        throw error;
      })
    );
  }

  createUser(user: User): Observable<User> {
    // Ensure ID is not sent for creation, or backend handles it
    const userData = { ...user, id: undefined }; // Or handle as needed by backend
    return this.http.post<User>(this.apiUrl, userData).pipe(
      catchError(error => {
        console.error('Error creating user:', error);
        throw error;
      })
    );
  }

  updateUser(user: User): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/${user.id}`, user).pipe(
      catchError(error => {
        console.error(`Error updating user with ID ${user.id}:`, error);
        throw error;
      })
    );
  }

  deleteUser(id: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/${id}`).pipe(
      catchError(error => {
        console.error(`Error deleting user with ID ${id}:`, error);
        throw error;
      })
    );
  }
}
