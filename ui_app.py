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

col1, col2 = st.columns((2))

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
    ['car_driver_id', 'eye_status']).size().reset_index(name='count')

# define mapping dictionary for eye_status labels
eye_status_labels = {0: "Open", 1: "Close"}
category_df['eye_status'] = category_df['eye_status'].map(
    eye_status_labels)  # replace numeric eye_status with labels

# pivot the dataframe for plotting grouped bars
pivot_df = category_df.pivot(
    index='car_driver_id', columns='eye_status', values='count').fillna(0)

# convert pivot dataframe to long format for plotting
plot_df = pivot_df.reset_index().melt(id_vars='car_driver_id',
                                      var_name='eye_status', value_name='count')
# filtered dataframe for eye_status = 0
eye_status_0_df = df[df["alarm_status"] == 0]

# group by car_driver_id and count occurrences of eye_status = 0 (open)
line_df = eye_status_0_df.groupby(
    'car_driver_id').size().reset_index(name='count')

if not line_df.empty:
    # create line chart
    line_fig = px.line(line_df, x="car_driver_id", y="count", title="Overall Performance of Car Driver",
                        labels={"car_driver_id": "Car Driver ID", "count": "Performance"})
    line_fig.update_yaxes(showticklabels=False)
    st.plotly_chart(line_fig, use_container_width=True)
else:
    st.subheader(
        "No data to display for line chart with selected filters.")
    
st.markdown("---")  # Create space between components

# bar chart
if not plot_df.empty:
    # define color mapping (dark blue for eye_status = 0, light blue for eye_status = 1)
    color_map = {'Open': '#1f77b4', 'Close': '#aec7e8'}

    # create bar chart with specified color mapping
    fig = px.bar(plot_df, x="car_driver_id", y="count", color="eye_status",
                    title="Eye Status Count",
                    labels={"car_driver_id": "Car Driver ID",
                            "count": "Count", "eye_status": "Eye Status"},
                    barmode="group",
                    color_discrete_map=color_map)

    # reorder legend items
    fig.update_layout(legend_traceorder="reversed")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.subheader("No data to display with selected filters.")
