sudo mkdir -p /var/www/multimetro
sudo tee /etc/nginx/sites-available/multimetro >/dev/null <<'CONF'
server {
  listen 80;
  server_name multimetro.wellgois.com;
  root /var/www/multimetro;
  index index.html;
  location / { try_files $uri $uri/ =404; }
}
CONF
sudo ln -sf /etc/nginx/sites-available/multimetro /etc/nginx/sites-enabled/multimetro
sudo nginx -t && sudo systemctl reload nginx
