# Planned work (not shipped)

The current package has a Chinese web UI, plus English and Chinese README/installation documents. Initialization asks for and confirms a panel password of at least 16 characters. Core credentials are random and separate. Web password change/reset is not implemented.

A future single package may offer Chinese/English switching: start from browser language, permit manual selection and remember it. Coverage should include login, devices, graphs, subscriptions, help, dialogs and backend error responses. This is a design direction, not a completed feature or release commitment.

Language is separate from routing policy. Current default rules and domestic DNS target the original mainland-China setup. Future configurable regional presets should be evaluated independently rather than assuming English makes this configuration appropriate everywhere.
