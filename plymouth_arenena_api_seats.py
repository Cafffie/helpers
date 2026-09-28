Now I have the full picture. The per-section endpoint /api/seatmaps/products/{perf_code}/sections/{section_code} 
returns real per-seat data with rows[].name (row letter) and seats[].name (seat number), seats[].isAvailable, seats[].status, 
and seats[].priceCategory. Let me read the config file, then write the implementation:
