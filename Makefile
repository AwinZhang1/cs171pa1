# Makefile
d ?= 10
epsilon_max ?= 0.1
rho ?= 1e-6
run_project:
	python3 time_server.py &
	python3 network.py &
	sleep 1
	python3 client.py --d $(d) --epsilon $(epsilon_max) --rho $(rho)