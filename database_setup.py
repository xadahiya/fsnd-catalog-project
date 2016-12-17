import os
import sys
import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()


class Category(Base):
    __tablename__ = 'category'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False, unique = True)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
         "name":self.name,
         "id":self.id,
       }




class Item(Base):
    __tablename__ = 'item'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    description = Column(String(500))
    date_added = Column(DateTime, default = datetime.datetime.utcnow)
    category_id = Column(Integer, ForeignKey('category.id'))
    category = relationship(Category)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
        "name":self.name,
        "description":self.description,
        "id":self.id,
        }


engine = create_engine('sqlite:///catalog.db')


Base.metadata.create_all(engine)
