# Item Catalog Project

>Christian Urrea

## About

The Item Catalog application provides a list of valuables within a variety of pawn shops.
This program uses third-party Oauth with Google for user registration and authentication system. 
Registered users will have the ability to create, edit and delete their own pawnshops and valuables within them.
Non-registered users will only be able to view pawn shops and their valuables.


### Dependencies
- Python 2.7.12
- SQLAlchemy==1.2.17
- Python-psycopg2==2.7.7
- Bootstrap
- Flask==1.0.2
- Jinja2==2.10
- oauth2client==4.1.3
- bleach==3.1.0
- chardet==3.0.4


### Instructions

1. Install [Vagrant](https://www.vagrantup.com/) and [VirtualBox](https://www.virtualbox.org/wiki/Downloads)
2. Launch the virtual machine with Vagrant: `vagrant up`
3. Login to the VM: `vagrant ssh`
3. Go to project directory: `cd /vagrant/catalog`
4. Set up application's databases:  `python database_setup.py`
5. Run application with `python application.py`
6. In your browser , go to `http://localhost/8000` to access the application locally

**if first time running, you must create a new pawn shop, and then add valuables to it**


#### CRUD Routes for Pawn Shops (Categories)
#### --------------------------------------

`/` or `/pawnshops` - returns list of all pawn shops

`/pawnshops/new` -  create a new pawn shop


`/pawnshops/<int:pawnshop_id>/edit/` - edit an existing pawn shop

`/pawnshops/<int:pawnshop_id>/delete/` - delete an existing pawn shop


#### CRUD Routes for Valuables (Items)
#### --------------------------------------

`/pawnshops/<int:pawnshop_id>/` or `/pawnshops/<int:pawnshop_id>/valuables/` - returns all valuables in pawn shop

`/pawnshops/<int:pawnshop_id>/valuables/new` - add a new valuable to pawn shop

`/pawnshops/<int:pawnshop_id>/valuables/<int:valuable_id>/edit` - update the information of valuable in pawn shop

`/pawnshops/<int:pawnshop_id>/valuables/<int:valuable_id>/delete` - delete a valuable from pawn shop


