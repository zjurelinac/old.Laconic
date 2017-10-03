# Laconic
*"Do everything with famous laconic brevity!"*

A Python web framework (for both Python 2 and 3, though 2 is not yet fully supported) that aims to make writting REST APIs in Python as fast and simple as it can possibly get.

It tries to accomplish that by turning otherwise repetitive and laborious tasks,
such as parsing request parameters, authentication, database communication,
response generation etc., into beautiful and expressive one-liners, which are
extremely simple to write and understand.

## Main features:
  - To be described...

## TODO:
  [ ] Core features
    [ ] Implement API regions and region-based event hooks & exception handlers
    [ ] Create most common return types - JSON, HTML, Binary etc., in a Python2-compatible way
    [ ] Create basic route param validators
  [ ] Documentation - Write comprehensive docs of every aspect of the framework
    [ ] Document app module
    [ ] Document context module
    [ ] Document routing module
    [ ] Document utilities module
    [ ] Document exception module
    [ ] Document types module
  [ ] Extra features
    [ ] Automatic API-doc generator - comment-based doc format
    [ ] Extend route attrs with docstring-parsed metadata
    [ ] Client app testing
      [ ] ...
    [ ] Database integration
      [ ] Custom or Peewee-based models?
        [ ] Fields extended with validation and formatting
      [ ] ViewModels?
        [ ] Precompile queries?
        [ ] Auto-generate stored procedures?
      [ ] Dynamic exception replacement
      [ ] Create model fast update method - if it doesn't exist already
      [ ] Investigate Peewee model capabilities and behaviour - select queries
    [ ] Frontend support
      [ ] Autogenerate Angular & Ember models and services/adapters
      [ ] Autogenerate curl examples, create Python SDK (and other langs)
    [ ] Extensions
      [ ] DEFINE EXTENSION TEMPLATE/INTERFACE
      [ ] Authentication - Basic, JWT, OAuth2
      [ ] Authorization
      [ ] Session
      [ ] Caching
      [ ] API access control & rate limits
      [ ] Stats & metrics
      [ ] Error-reporting, extensive logging
      [ ] Security - CORS, XSRF
      [ ] Task running
  [ ] Bugfixes
    [ ] Endpoint with no return type specified fails with exception
