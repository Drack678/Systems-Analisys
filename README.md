# 🚍 UMOS Project

## 📌 Project Overview

The **Urban Mobility Optimization System (UMOS)** is a multimodal route planning and optimization platform designed to improve transportation efficiency for the **Universidad Distrital Francisco José de Caldas** community in Bogotá, Colombia.

This repository contains:
- Systems Analysis (Workshop 1)
- System Design (Workshop 2)

The project addresses key inefficiencies in urban mobility, including:
- Peak-hour congestion  
- Long waiting times  
- Rain-related disruptions  
- Equity issues in public transportation (TransMilenio, SITP, bicycles)  

---

## 🧠 Workshop 1: Systems Analysis

This phase decomposes UMOS into four main subsystems:
- Physical transport  
- Fleet operations  
- Information / digital systems  
- Governance and policy  

### 🔍 Key Findings

Based on surveys (**n = 312**), observations, and collected data:

- ⏰ Peak demand between **07:30–08:15** leads to **25–28 minute waiting times**  
- 🌧️ Rain increases waiting times by **63%**  
- 🚴 Bike usage drops by **93.5%** during rain  
- 💰 Users from southern areas face **higher cost per km**, revealing inequities  
- 🚧 Major bottlenecks:
  - Ak 7 mixed-traffic corridor  
  - Estación Universidades hub  

---

## ⚙️ Workshop 2: System Design

This phase builds on the analysis by proposing a **modular microservices architecture** using:

- **Backend:** NestJS  
- **Frontend:** React Native  
- **Infrastructure:** Google Kubernetes Engine (GKE)  
- **Database:** PostgreSQL + PostGIS  

### 🚀 Key Features

- Real-time data integration:
  - GTFS-RT (public transport)
  - Traffic data
  - Weather services  

- Intelligent route optimization  
- Notification system for alerts and disruptions  
- Risk mitigation strategies:
  - Circuit breakers  
  - Horizontal Pod Autoscaler (HPA)  

### 🎯 System Targets

- ✅ 99.5% uptime  
- ⚡ ~14,000 events per minute under peak load  
- 🌍 Improved equitable access to transportation  

---

## 👥 Authors and Contact

### 👩‍💻 Natalie Marino Figueroa  
- ID: 20232020143  
- Dept. of Computer Engineering  
- Universidad Distrital Francisco José de Caldas  
- 📧 nmarinof@udistrital.edu.co  

---

### 👨‍💻 Edilson Santiago Sepúlveda Cortés  
- ID: 20231020237  
- Dept. of Computer Engineering  
- Universidad Distrital Francisco José de Caldas  
- 📧 essepulvedac@udistrital.edu.co  

---

### 👨‍💻 Marlon Yecid Riveros Guio  
- ID: 20231020208  
- Dept. of Computer Engineering  
- Universidad Distrital Francisco José de Caldas  
- 📧 myriverosg@udistrital.edu.co  

---

### 👨‍💻 Juan Esteban Cañón Solorza  
- ID: 20232020078  
- Dept. of Computer Engineering  
- Universidad Distrital Francisco José de Caldas  
- 📧 jecanons@udistrital.edu.co  

---

## 📍 Location

Bogotá, Colombia  

---

## 📄 License

This project is developed for academic purposes.
