[ -d /opt/eletrodiag ] && git -C /opt/eletrodiag pull || sudo git clone https://github.com/wellgois/eletrodiag /opt/eletrodiag
sudo cp /opt/eletrodiag/app/index.html /var/www/multimetro/index.html
sudo mkdir -p /var/www/multimetro/painel
sudo cp /opt/eletrodiag/bi/dashboard/index.html /var/www/multimetro/painel/index.html
