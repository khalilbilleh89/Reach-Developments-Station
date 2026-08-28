"""Shared application infrastructure.

`app.core` must never import a business domain module. Dependencies flow in one
direction only:  app.core  <-  domain modules  <-  API composition.
"""
