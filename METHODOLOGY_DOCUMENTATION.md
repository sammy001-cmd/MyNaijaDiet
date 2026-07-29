# MyNaijaDiet: Methodology and System Documentation

## 1. Project Overview

MyNaijaDiet is a web-based intelligent diet recommendation system developed to help users in Nigeria and other similar contexts receive meal suggestions that are personalized to their health profile, nutritional goals, cultural food preferences, and budget constraints. The system combines a Django web application with machine learning-based meal recommendation and a rule-based meal planning engine.

The project was designed around three main objectives:

1. To help users create a personalized health profile.
2. To recommend meals that align with their health goals such as weight loss, maintenance, or weight gain.
3. To generate realistic daily and weekly meal plans using local Nigerian food options.

---

## 2. Problem Statement

Many nutrition and meal-planning systems are built around generic Western dietary patterns and are not well adapted to local food culture, affordability, and meal structure. In the Nigerian context, users often need recommendations based on local dishes, regional food preferences, and common meal timing patterns.

This project addresses that gap by building a recommender system that:

- uses local meal data,
- incorporates user-specific health information,
- recommends meals based on nutrition and suitability,
- generates practical meal plans for real-life use,
- and allows users to provide feedback to improve future recommendations.

---

## 3. Research and Development Approach

The project followed a practical applied research approach that combined:

- data preparation and preprocessing,
- supervised machine learning for meal-goal classification,
- web application development for user interaction,
- recommendation logic for ranking meals,
- and a feedback-informed planning system.

The overall development workflow consisted of the following stages:

1. Data collection and preparation.
2. Feature engineering and preprocessing.
3. Training and evaluation of multiple machine learning models.
4. Integration of the best-performing model into the Django application.
5. Development of meal planning, recommendation, and user feedback modules.
6. Deployment of the system as a usable web platform.

---

## 4. System Architecture

The system is organized into the following major components:

### 4.1 Web Application Layer
The web application is built with Django and provides the main interface for:

- user registration and authentication,
- health profile management,
- meal browsing and recommendations,
- meal plan generation,
- user feedback submission,
- and staff/admin moderation workflows.

### 4.2 Database Layer
The application uses a relational database managed through Django models. Main entities include:

- User
- HealthProfile
- Meal
- MealPlan
- MealPlanEntry
- Recommendation
- MealFeedback
- MealEdit

### 4.3 Machine Learning Layer
The ML layer trains models to predict the most suitable meal goal category for a given meal. The target variable is:

- weight_loss
- maintenance
- muscle_gain

The trained models are stored and later used by the application for scoring and ranking meals.

### 4.4 Recommendation and Planning Layer
The recommendation system uses the trained model to score meals and ranks them according to their relevance to the user’s health goal. The meal planner then uses these scores along with calorie budgets, variety rules, and food-family restrictions to generate a structured weekly plan.

---

## 5. Data Sources

The main dataset used in this study is the file named:

- mynaijadiet_dataset_v2.csv

This dataset contains meal records with nutritional and categorical attributes. Each meal entry includes attributes such as:

- food_name
- category
- region
- meal_time
- calories_kcal
- protein_g
- carb_g
- fat_g
- goal_suitability
- diet_type
- taste_profile
- prep_time
- price_range

The data reflects a nutrition-focused meal dataset adapted to a Nigerian meal context, with local dishes and culturally relevant food labels.

---

## 6. Data Preprocessing

Before model training, the raw dataset underwent a structured preprocessing pipeline.

### 6.1 Data Loading and Inspection
The raw CSV data was loaded into a pandas DataFrame and inspected to understand its shape, columns, and quality.

### 6.2 Meal-Time Expansion
The original meal_time field was a comma-separated string. This was expanded into binary indicator columns for the following meal slots:

- breakfast
- lunch
- dinner
- snack

This enabled the models to interpret meal availability more effectively.

### 6.3 Ordinal Encoding
Some categorical variables reflect ordered levels and were encoded manually to preserve their rank relationships. Examples included:

- prep_time: short < medium < long
- price_range: low < medium < high
- goal_suitability: weight_loss < maintenance < muscle_gain
- diet_type: ordered by nutritional intent
- category: ordered based on general meal placement patterns

### 6.4 One-Hot Encoding
Nominal variables such as region and taste_profile were transformed using one-hot encoding so that the models could treat them as categorical features without imposing artificial ordering.

### 6.5 Feature Engineering
Several engineered features were created to improve model reasoning, including:

- macro_ratio_protein
- macro_ratio_carb
- macro_ratio_fat
- calorie_density
- protein_per_100kcal

These features were included to capture the nutritional profile of each meal more effectively.

### 6.6 Normalization
Numeric features were scaled to a common range using MinMaxScaler to improve model convergence and stability.

### 6.7 Output Files
The preprocessing stage produced files such as:

- mynaijadiet_processed.csv 
- meal_id_map.csv
- encoder files for ordinal maps, nominal categories, and scaler values

---

## 7. Machine Learning Methodology

### 7.1 Target Variable
The classification problem was framed as multiclass classification. The target variable, goal_suitability, was used to predict whether a meal is best suited for:

- weight loss,
- maintenance,
- or muscle gain.

### 7.2 Models Trained
The following models were trained and evaluated:

- Random Forest
- LightGBM
- Artificial Neural Network (ANN)
- LSTM
- Ensemble (average of model probabilities)

### 7.3 Training Strategy
The data was split using a stratified train-test split to preserve class balance across the training and testing subsets. Model performance was evaluated using:

- accuracy
- cross-validation accuracy
- and classification reports

### 7.4 Results Summary
The current model evaluation results recorded in the project are:

- Random Forest: 0.88 test accuracy, 0.8195 CV accuracy
- LightGBM: 0.88 test accuracy, 0.8304 CV accuracy
- ANN: 0.8667 test accuracy
- LSTM: 0.64 test accuracy
- Ensemble: 0.8667 test accuracy

### 7.5 Model Selection
Although several models performed well, LightGBM was selected for the production recommendation pipeline because it achieved strong performance while being faster and lighter than the deep learning alternatives. This was an important design decision because the application needs to provide low-latency recommendations in a web environment.

---

## 8. Recommendation Engine Design

The recommendation engine works as follows:

1. The system receives the user’s health goal.
2. All meals are encoded into the same feature format used during training.
3. The trained LightGBM model scores each meal.
4. The meals are ranked according to the predicted suitability for the user’s goal.
5. The top-ranked meals are presented in the recommendation page and used by the meal planner.

The implementation is handled in the recommendation engine module, where each meal is converted into a feature vector and assigned a prediction probability.

---

## 9. Meal Planning Methodology

The meal planner generates daily and weekly meal plans using both machine learning scores and rule-based constraints.

### 9.1 Planning Logic
The planner uses the following logic:

- Assigns calorie budgets to each meal slot based on the user’s daily target.
- Uses ML scores to prioritize appropriate meals.
- Applies variety rules to avoid repeated food families too frequently.
- Prevents multiple different swallow-based meals on the same day.
- Uses feedback-aware adjustment so meals that users disliked receive lower ranking.

### 9.2 Constraints Applied
The planner includes several hard and soft constraints:

- meal slot compatibility (breakfast, lunch, dinner, snack)
- calorie budget tolerance
- food-family variety
- daily variety rules
- weekly repetition limits

### 9.3 Output
The meal planner produces a structured plan containing multiple meal slots across several days. Each meal plan entry includes:

- the meal assigned,
- the day number,
- the meal slot,
- portion size,
- and a match score.

---

## 10. User Interaction and Application Workflow

### 10.1 Registration and Profile Setup
New users can register and create a health profile with details such as:

- age
- gender
- weight
- height
- activity level
- health goal
- regional preference
- and medical flags such as diabetes, hypertension, or vegetarian status

The system uses this information to calculate:

- BMI
- BMR
- TDEE
- and a personalized daily calorie target

### 10.2 Dashboard
Users are presented with a dashboard containing:

- a personalized greeting,
- calorie and macro targets,
- current meal plan information,
- and AI-generated meal recommendations.

### 10.3 Recommendations Page
Users can browse meals, filter them by meal time or region, search for meals, and view the predicted relevance score for each meal.

### 10.4 Meal Detail and Feedback
Users can view meal details and leave feedback after trying a meal. This feedback is later used to adjust future ranking and planning decisions.

### 10.5 Meal Plan Management
Users can:

- view their current plan,
- swap meals,
- add meals manually,
- and remove entries.

---

## 11. Staff and Content Moderation Workflow

To ensure meal data quality, the project includes a staff moderation and proposal workflow.

Staff users can:

- propose new meals,
- propose edits to existing meals,
- propose deletions,
- and review their own submissions.

Superusers can:

- approve or reject proposals,
- apply approved edits directly to the live meal dataset,
- and manage meal records.

This component is important because it supports data quality, governance, and content curation for the recommendation system.

---

## 12. Database Design Summary

The project uses Django ORM models to represent all major entities. The core domain model is centered around meals and user health. The most important relational structures are:

- User → HealthProfile (one-to-one)
- User → MealPlan (one-to-many)
- MealPlan → MealPlanEntry (one-to-many)
- User → Recommendation (one-to-many)
- User → MealFeedback (one-to-many)
- Meal → MealEdit (one-to-many)

This structure allows the system to maintain personalized plans, persistent recommendations, and reviewable content proposals.

---

## 13. Technical Implementation Summary

The main technologies used in the project are:

- Python
- Django
- SQLite (development database)
- pandas
- scikit-learn
- LightGBM
- TensorFlow/Keras (for experimental deep learning models)
- Pillow and Cloudinary (for image handling)
- HTML/CSS/JavaScript templates for the frontend

The system was implemented in a modular way, with separate components for:

- models,
- views,
- forms,
- URLs,
- machine learning logic,
- meal planning logic,
- and templates.

---

## 14. Evaluation and Justification of the Final Approach

The project compared several model families and selected LightGBM as the primary model for deployment. The decision was justified by the following points:

- strong predictive accuracy,
- competitive cross-validation performance,
- lower computational cost than ANN/LSTM,
- faster inference for a web system,
- and simpler deployment requirements.

This makes the system practical for real-world use in a lightweight web application environment.

---

## 15. Limitations and Challenges

Although the project is functional and well structured, several limitations remain:

- The dataset is relatively small and domain-specific.
- The recommendation system is still partly rule-based and not fully adaptive to every user’s complex dietary needs.
- Some health recommendations are simplified and should not replace professional medical advice.
- The system currently emphasizes meal suitability and meal-plan construction more than full clinical nutrition modeling.

These limitations are important to acknowledge in any academic or professional methodology section.

---

## 16. Contribution of the Project

This project contributes to the field of personalized nutrition support by demonstrating a practical system that combines:

- personalized health profiling,
- meal classification with machine learning,
- cultural food relevance,
- intelligent meal planning,
- and user feedback integration.

It is especially relevant for contexts where users need digital support that reflects local food traditions and practical meal habits.

---

## 17. Suggested Methodology Summary for Academic Use

A concise methodology summary suitable for a thesis, dissertation, or report could be written as follows:

“This study developed MyNaijaDiet, an intelligent web-based meal recommendation and planning system for personalized nutrition support. The system was built using Django and machine learning techniques, with meal suitability modeled as a multiclass classification problem. A preprocessing pipeline was applied to transform meal attributes into model-ready features, and several classifiers including Random Forest, LightGBM, ANN, LSTM, and an ensemble were evaluated. LightGBM was selected for deployment due to its strong accuracy and efficiency. The system integrates user health profiles, nutritional goals, cultural food preferences, and feedback mechanisms to generate personalized meal recommendations and weekly meal plans.”

---

## 18. Key Project Files

The main files and modules involved in the implementation are:

- [recommender/models.py](recommender/models.py)
- [recommender/views.py](recommender/views.py)
- [recommender/ml_engine.py](recommender/ml_engine.py)
- [recommender/meal_planner.py](recommender/meal_planner.py)
- [encoders/preprocessing.py](encoders/preprocessing.py)
- [train_models.py](train_models.py)
- [check_models.py](check_models.py)
- [smart_diet_project/settings.py](smart_diet_project/settings.py)
- [recommender/ml/model_results.csv](recommender/ml/model_results.csv)

---

## 19. Conclusion

MyNaijaDiet demonstrates a complete pipeline from data preparation to intelligent recommendation and practical meal planning. The project combines machine learning, web development, user personalization, and food-data curation into a working system that can be extended into a more advanced nutrition assistant in the future.
