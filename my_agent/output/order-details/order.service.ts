import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

// Define interfaces for Order and OrderItem for better type safety
export interface OrderItem {
  productName: string;
  quantity: number;
  price: number;
  subtotal: number;
}

export interface Order {
  id: string;
  customerName: string;
  orderDate: string; // Assuming string, adjust if it's Date
  totalAmount: number;
  items: OrderItem[];
}

@Injectable({
  providedIn: 'root'
})
export class OrderService {
  private apiUrl = '/api/orders'; // Base API URL for orders

  constructor(private http: HttpClient) { }

  // Fetches a list of all orders (can be used for an orders overview page)
  getOrders(): Observable<Order[]> {
    return this.http.get<Order[]>(`${this.apiUrl}`)
      .pipe(
        catchError(error => {
          console.error('Error fetching orders:', error);
          return of([]); // Return empty array on error
        })
      );
  }

  // Fetches details for a specific order by ID
  getOrderById(id: string): Observable<Order> {
    return this.http.get<Order>(`${this.apiUrl}/${id}`)
      .pipe(
        catchError(error => {
          console.error(`Error fetching order with ID ${id}:`, error);
          // Return a specific error or an observable that throws an error
          // For now, re-throwing the error to be caught by the component
          throw error;
        })
      );
  }
}
