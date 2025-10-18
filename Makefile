# Makefile
d ?= 10
epsilon_max ?= 0.1
rho ?= 1e-6

run_project:
	@-pkill -9 -f "python3 time_server.py" 2>/dev/null || true
	@-pkill -9 -f "python3 network.py" 2>/dev/null || true
	@sleep 1
	python3 time_server.py > /dev/null 2>&1 & echo $$! > .time_server.pid
	python3 network.py > /dev/null 2>&1 & echo $$! > .network.pid
	@sleep 1
	-python3 client.py --d $(d) --epsilon $(epsilon_max) --rho $(rho)
	@kill `cat .time_server.pid 2>/dev/null` 2>/dev/null || true
	@kill `cat .network.pid 2>/dev/null` 2>/dev/null || true
	@rm -f .time_server.pid .network.pid

clean:
	@-pkill -9 -f "python3 time_server.py" 2>/dev/null || true
	@-pkill -9 -f "python3 network.py" 2>/dev/null || true
	@rm -f *.pid *.csv

.PHONY: run_project clean
