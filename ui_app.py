import streamlit as st
import plotly.express as px
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

# headline
st.set_page_config(page_title="Superstore!!!",
                   page_icon=":clipboard:", layout="wide")

st.title(" :clipboard: Car Rental Database")
st.markdown(
    '<style>div.block-container{padding-top:1rem;}</style>', unsafe_allow_html=True)

# upload csv
fl = st.file_uploader(":file_folder: Upload a file",
                      type=(["csv", "txt", "xlsx", "xls"]))
if fl is not None:
    filename = fl.name
    st.write(filename)
    df = pd.read_csv(filename, encoding="ISO-8859-1")
else:
    os.chdir(r"C:\Users\Fern\Desktop\Ict720_software_2024")
    df = pd.read_csv("20240501075148_device_events.csv", encoding="ISO-8859-1")

# show dataframe
show_df_button = st.button("Show Dataframe!")
if show_df_button:
    st.dataframe(df)

# create for car
st.sidebar.header("Choose the filter: ")
car = st.sidebar.multiselect("Pick Car", df["dev_id"].unique())
if not car:  # if not select car
    df2 = df.copy()
else:  # choose specific car
    df2 = df[df["dev_id"].isin(car)]

# create for driver
driver = st.sidebar.multiselect("Pick Driver", df["car_driver_id"].unique())
if not driver:  # if not select driver
    df3 = df2.copy()
else:  # choose specific driver
    df3 = df2[df2["car_driver_id"].isin(driver)]

filtered_df = df3

# group by car_driver_id and eye_status
category_df = filtered_df.groupby(
    ['car_driver_id', 'eye_status']).size().reset_index(name='eye_status_count')

# define mapping dictionary for eye_status labels
eye_status_labels = {0: "Open", 1: "Close"}
category_df['eye_status'] = category_df['eye_status'].map(
    eye_status_labels)  # replace numeric eye_status with labels

# pivot the dataframe for plotting grouped bars
pivot_df = category_df.pivot(
    index='car_driver_id', columns='eye_status', values='eye_status_count').fillna(0)

# convert pivot dataframe to long format for plotting
plot_df = pivot_df.reset_index().melt(id_vars='car_driver_id',
                                      var_name='eye_status', value_name='eye_status_count')

# filtered dataframe for alarm_status = 0
alarm_status_0_df = df[df["alarm_status"] == 0]

# group by car_driver_id and count occurrences of alarm_status = 0 (no alarm)
alarm_line_df = alarm_status_0_df.groupby(
    'car_driver_id').size().reset_index(name='alarm_count')

if not alarm_line_df.empty:
    # create line chart for alarm count
    alarm_line_fig = px.line(alarm_line_df, x="car_driver_id", y="alarm_count", title="Overall Performance of Car Driver (Evaluated by The Number of Times of The Alarm)",
                             labels={"car_driver_id": "Car Driver ID", "alarm_count": "Performance"})
    alarm_line_fig.update_yaxes(showticklabels=False)
    st.plotly_chart(alarm_line_fig, use_container_width=True)
else:
    st.subheader("No data to display for line chart with selected filters.")

st.markdown("---")  # Create space between components

col1, col2 = st.columns((2))

with col1:
    # bar chart for eye status count
    if not plot_df.empty:
        # define color mapping (dark blue for eye_status = 0, light blue for eye_status = 1)
        eye_status_color_map = {'Open': '#1f77b4', 'Close': '#aec7e8'}

        # create bar chart for eye status count with specified color mapping
        eye_status_fig = px.bar(plot_df, x="car_driver_id", y="eye_status_count", color="eye_status",
                                title="Eye Status Count",
                                labels={"car_driver_id": "Car Driver ID",
                                        "eye_status_count": "Count", "eye_status": "Eye Status"},
                                barmode="group", color_discrete_map=eye_status_color_map)

        # reorder legend items
        eye_status_fig.update_layout(legend_traceorder="reversed")
        st.plotly_chart(eye_status_fig, use_container_width=True)
    else:
        st.subheader(
            "No data to display for eye status count with selected filters.")

# Group by car_driver_id and alarm_status
alarm_category_df = filtered_df.groupby(
    ['car_driver_id', 'alarm_status']).size().reset_index(name='alarm_count')

# Define mapping dictionary for alarm_status labels
alarm_status_labels = {0: "No Alarm", 1: "Alarm"}
alarm_category_df['alarm_status'] = alarm_category_df['alarm_status'].map(
    alarm_status_labels)

# Pivot the dataframe for plotting grouped bars
alarm_pivot_df = alarm_category_df.pivot(
    index='car_driver_id', columns='alarm_status', values='alarm_count').fillna(0)

# Convert pivot dataframe to long format for plotting
alarm_plot_df = alarm_pivot_df.reset_index().melt(
    id_vars='car_driver_id', var_name='alarm_status', value_name='alarm_count')

with col2:
    # check if data is available to plot
    if not alarm_plot_df.empty:
        # Define color mapping (e.g., green for no alarm, red for alarm)
        alarm_color_map = {'No Alarm': '#2ca02c', 'Alarm': '#d62728'}

        # Create bar chart with specified color mapping for alarm status count
        alarm_fig = px.bar(alarm_plot_df, x="car_driver_id", y="alarm_count", color="alarm_status",
                           title="Alarm Status Count by Car Driver",
                           labels={"car_driver_id": "Car Driver ID",
                                   "alarm_count": "Count", "alarm_status": "Alarm Status"},
                           barmode="group", color_discrete_map=alarm_color_map)

        # Reorder legend items
        alarm_fig.update_layout(legend_traceorder="reversed")
        st.plotly_chart(alarm_fig, use_container_width=True)
    else:
        st.subheader(
            "No data to display for alarm status count with selected filters.")
